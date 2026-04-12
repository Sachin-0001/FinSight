from __future__ import annotations

import json
import re
from dataclasses import dataclass
from random import Random
from typing import Any, Dict, List, Tuple

from models import FinancialAction
from server.data_generator import (
    ISSUE_CATALOG,
    build_balance_sheet_issue_case,
    build_income_statement_case,
    build_transaction_case,
    generate_balance_sheet_with_issues,
    generate_income_statement,
    generate_transaction_log,
)


@dataclass(frozen=True)
class TaskDefinition:
    name: str
    difficulty: str
    document_type: str
    description: str
    legal_actions: List[str]


TASKS: Dict[str, TaskDefinition] = {
    "anomaly_classification": TaskDefinition(
        name="anomaly_classification",
        difficulty="easy",
        document_type="transaction_log",
        description=(
            "Find anomalous transactions and return comma-separated transaction IDs in action.value "
            "when action_type is 'classify'."
        ),
        legal_actions=["classify"],
    ),
    "kpi_extraction": TaskDefinition(
        name="kpi_extraction",
        difficulty="medium",
        document_type="income_statement",
        description=(
            "Extract KPI JSON with keys revenue, gross_profit, net_income, ebitda in action.value "
            "when action_type is 'extract_kpi'."
        ),
        legal_actions=["extract_kpi"],
    ),
    "compliance_assessment": TaskDefinition(
        name="compliance_assessment",
        difficulty="hard",
        document_type="balance_sheet",
        description=(
            "Flag compliance issues in JSON format {'issues':[...]} in action.value when action_type is 'flag_issue'."
        ),
        legal_actions=["flag_issue"],
    ),
}


def _clamp_score(score: float) -> float:
    """Ensure score is between 0 and 1 (inclusive)."""
    return max(0.0, min(1.0, score))


# FIX: removed the broken int-typed _clamp that was silently corrupting float scores.
# All callers now use _clamp_score (float-safe) directly.


def _f1_strict(predicted: List[str], truth: List[str]) -> float:
    pred_set = {p.strip() for p in predicted if p and p.strip()}
    true_set = {t.strip() for t in truth if t and t.strip()}
    if not true_set:
        return 1.0 if not pred_set else 0.0
    if not pred_set:
        return 0.0
    tp = len(pred_set & true_set)
    precision = tp / len(pred_set)
    recall = tp / len(true_set)
    if precision + recall == 0:
        return 0.0
    return (2 * precision * recall) / (precision + recall)


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _apply_global_quality_penalties(base_score: float, action: FinancialAction) -> float:
    score = base_score
    if action.confidence > 0.85 and score < 0.5:
        score -= 0.1
    if len(action.reasoning.strip()) < 20:
        score -= 0.05
    # FIX: use _clamp_score (float) instead of the old _clamp (int-typed, corrupted floats).
    return _clamp_score(score)


# ---------------------------------------------------------------------------
# ANOMALY CLASSIFICATION
# ---------------------------------------------------------------------------

def grade_anomaly_classification(
    action: FinancialAction, ground_truth: Dict[str, Any], seed: int
) -> float:
    value = action.value.strip()
    predictions = [piece.strip() for piece in value.split(",") if piece.strip()]

    true_anomaly_ids: List[str] = list(ground_truth["anomaly_ids"])
    # FIX: also pull the distractors so the grader knows which high-amount rows
    # are explicitly NOT anomalies — used below to avoid false-positive punishment
    # for the unlisted office_supplies row (see data_generator bug note).
    distractor_ids: List[str] = list(ground_truth.get("distractor_ids", []))

    num_anomalies = int(ground_truth.get("num_anomalies", 5 if seed % 2 == 0 else 4))
    tx_case = build_transaction_case(seed=seed, num_anomalies=num_anomalies)
    rows_by_id = {str(r["id"]): r for r in tx_case["rows"]}

    # Expand ground truth for office_supplies > $5k rows not listed in anomaly_ids (generator edge case).
    extended_truth = set(true_anomaly_ids)

    for pid in predictions:
        if pid not in distractor_ids and pid not in extended_truth:
            # Check if this row looks anomalous: office_supplies amount > 5000
            # We do this by checking against the regenerated case (cheap, seeded).
            row = rows_by_id.get(pid)
            if row and row.get("vendor_category") == "office_supplies" and float(row.get("amount", 0)) > 5000:
                extended_truth.add(pid)

    base = _f1_strict(predictions, list(extended_truth))
    return _apply_global_quality_penalties(base, action)


# ---------------------------------------------------------------------------
# KPI EXTRACTION
# ---------------------------------------------------------------------------

def grade_kpi_extraction(
    action: FinancialAction, ground_truth: Dict[str, Any], seed: int
) -> float:
    _ = seed
    invalid_penalty = 0.0
    payload: Dict[str, Any] = {}
    try:
        parsed = json.loads(action.value)
        if isinstance(parsed, dict):
            payload = parsed
        else:
            invalid_penalty = -0.15
    except json.JSONDecodeError:
        invalid_penalty = -0.15

    keys = ["revenue", "gross_profit", "net_income", "ebitda"]
    per_kpi_scores: List[float] = []

    for key in keys:
        actual = float(ground_truth[key])
        predicted = _safe_float(payload.get(key))

        if predicted is None:
            per_kpi_scores.append(0.0)
            continue

        if actual == 0:
            per_kpi_scores.append(1.0 if predicted == 0 else 0.0)
            continue

        rel_err = abs(predicted - actual) / abs(actual)

        if rel_err <= 0.005:
            metric_score = 1.0
        elif rel_err >= 0.15:
            # FIX: raised the zero-score threshold from 0.08 → 0.15.
            # The original 0.08 was too tight: a model that returns a value in
            # thousands instead of full USD (off by 1000×) gets the same 0 as one
            # that's 9% off.  At 0.15 we still penalise wrong-unit answers heavily
            # while giving real partial credit for close-but-not-perfect values.
            metric_score = 0.0
        else:
            # FIX: smooth linear interpolation over the wider [0.005, 0.15] band
            # instead of the old [0.005, 0.08] band, producing continuous scores
            # rather than a spike at 0.5.
            metric_score = 1.0 - ((rel_err - 0.005) / 0.145)

        per_kpi_scores.append(metric_score)

    # FIX: removed the 0.25-per-missing-KPI flat penalty that was creating the
    # 0.5 spike.  Missing keys already score 0.0 in per_kpi_scores, so they are
    # already penalised proportionally via the mean — double-penalising them
    # pushed the achievable score floor to exactly 0.5 for 3-correct / 1-missing.
    base = (sum(per_kpi_scores) / len(keys)) + invalid_penalty
    return _apply_global_quality_penalties(base, action)


# ---------------------------------------------------------------------------
# COMPLIANCE ASSESSMENT
# ---------------------------------------------------------------------------

def _extract_issue_payload(value: str) -> Tuple[List[Dict[str, Any]], int]:
    value = value.strip()

    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        issue_pattern = re.compile(
            r'\{"type":\s*"([^"]+)",\s*"severity":\s*"([^"]+)",\s*"description":\s*"([^"]+)"\}',
            re.DOTALL,
        )
        matches = issue_pattern.findall(value)
        if matches:
            recovered: List[Dict[str, Any]] = []
            for type_val, sev_val, desc_val in matches:
                recovered.append(
                    {
                        "type": type_val.strip(),
                        "severity": sev_val.strip().lower(),
                        "description": desc_val.strip(),
                    }
                )
            return recovered, 0
        return [], 0

    issues = payload.get("issues", []) if isinstance(payload, dict) else []
    if not isinstance(issues, list):
        return [], 0

    normalized: List[Dict[str, Any]] = []
    hallucinations = 0
    for issue in issues:
        if not isinstance(issue, dict):
            hallucinations += 1
            continue
        issue_type = issue.get("type")
        if not isinstance(issue_type, str) or not issue_type.strip():
            hallucinations += 1
            continue
        severity = issue.get("severity", "")
        normalized.append(
            {
                "type": issue_type.strip(),
                "severity": severity.strip().lower() if isinstance(severity, str) else "",
            }
        )

    return normalized, hallucinations


def grade_compliance_assessment(
    action: FinancialAction, ground_truth: Dict[str, Any], seed: int
) -> float:
    _ = seed
    predicted_issues, parsing_hallucinations = _extract_issue_payload(action.value)
    pred_map = {item["type"]: item.get("severity", "") for item in predicted_issues}

    true_issues: List[Dict[str, str]] = ground_truth["issues"]
    severity_weight = {"high": 1.0, "medium": 0.6, "low": 0.3}
    true_map = {issue["type"]: issue["severity"] for issue in true_issues}

    # The compliance grader uses explicit issue-type slugs for red herrings.
    red_herring_slugs: set[str] = set()  # populated below from ground_truth if available
    raw_rh = ground_truth.get("red_herring_slugs", [])
    if raw_rh:
        red_herring_slugs = set(raw_rh)

    weighted_tp = 0.0
    weighted_total = 0.0
    for issue_type, truth_severity in true_map.items():
        issue_weight = severity_weight.get(truth_severity, 0.3)
        weighted_total += issue_weight
        if issue_type in pred_map:
            if pred_map[issue_type] == truth_severity:
                weighted_tp += issue_weight
            else:
                weighted_tp += issue_weight * 0.5

    false_positive_types = [
        ptype for ptype in pred_map
        if ptype not in true_map and ptype not in red_herring_slugs
    ]
    red_herring_flags = [ptype for ptype in pred_map if ptype in red_herring_slugs]

    precision_denom = weighted_tp + len(false_positive_types)
    precision = weighted_tp / precision_denom if precision_denom > 0 else 0.0
    recall = weighted_tp / weighted_total if weighted_total > 0 else 0.0

    if precision + recall == 0:
        f1_like = 0.0
    else:
        f1_like = (2 * precision * recall) / (precision + recall)

    hallucination_count = len(false_positive_types) + parsing_hallucinations
    hallucination_penalty = max(-0.3, -0.15 * hallucination_count)
    red_herring_penalty = -0.15 * len(red_herring_flags)

    base = _clamp_score(f1_like + hallucination_penalty + red_herring_penalty)
    return _apply_global_quality_penalties(base, action)


# ---------------------------------------------------------------------------
# TASK INSTANCE GENERATION + GRADING
# ---------------------------------------------------------------------------

def generate_task_instance(task_name: str, seed: int) -> Dict[str, Any]:
    if task_name not in TASKS:
        raise ValueError(f"Unknown task_name: {task_name}")

    task = TASKS[task_name]

    if task_name == "anomaly_classification":
        anomaly_count = 5 if seed % 2 == 0 else 4
        tx_case = build_transaction_case(seed=seed, num_anomalies=anomaly_count)
        content = generate_transaction_log(seed=seed, num_anomalies=anomaly_count)
        ground_truth = {
            "anomaly_ids": tx_case["anomaly_ids"],
            "distractor_ids": tx_case["distractor_ids"],
            "num_anomalies": anomaly_count,
            "seed": seed,
        }
    elif task_name == "kpi_extraction":
        income_case = build_income_statement_case(seed=seed)
        content = generate_income_statement(seed=seed)
        ground_truth = {
            "revenue": income_case["restated"]["revenue"],
            "gross_profit": income_case["restated"]["gross_profit"],
            "net_income": income_case["restated"]["net_income"],
            "ebitda": income_case["restated"]["ebitda"],
            "seed": seed,
        }
    else:
        rng = Random(seed)
        all_types = list(ISSUE_CATALOG.keys())
        selected_count = 5 if seed % 2 == 0 else 6
        core_types = [
            "debt_covenant_breach_risk",
            "related_party_transactions",
            "revenue_recognition_irregularity",
        ]
        must_include = rng.sample(core_types, k=2)
        remaining = [t for t in all_types if t not in must_include]
        rng.shuffle(remaining)
        selected_types = must_include + remaining[: selected_count - len(must_include)]
        issue_case = build_balance_sheet_issue_case(seed=seed, issue_types=selected_types)
        content = generate_balance_sheet_with_issues(seed=seed, issue_types=selected_types)
        ground_truth = {
            "issues": issue_case["issues"],
            "red_herrings": issue_case["red_herrings"],
            "red_herring_slugs": issue_case.get("red_herring_slugs", []),
            "seed": seed,
        }

    return {
        "task": task,
        "document": content,
        "ground_truth": ground_truth,
    }


def grade_task(task_name: str, action: FinancialAction, ground_truth: Dict[str, Any]) -> float:
    seed = int(ground_truth.get("seed", 0))
    if task_name == "anomaly_classification":
        return grade_anomaly_classification(action, ground_truth, seed)
    if task_name == "kpi_extraction":
        return grade_kpi_extraction(action, ground_truth, seed)
    if task_name == "compliance_assessment":
        return grade_compliance_assessment(action, ground_truth, seed)
    raise ValueError(f"Unknown task_name: {task_name}")