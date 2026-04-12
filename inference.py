from __future__ import annotations

import json
import os
import re
from statistics import mean
from typing import Any, Dict, List
from datetime import datetime

from dotenv import load_dotenv
import httpx
from openai import OpenAI

from client import FinancialDocEnv
from models import FinancialAction

TASK_TO_KEY = {
    "anomaly_classification": "task_easy",
    "kpi_extraction": "task_medium",
    "compliance_assessment": "task_hard",
}


def _bounded_score(value: float) -> float:
    """Clamp to [0, 1] for reporting."""
    return max(0.0, min(1.0, float(value)))


def _assert_env_is_reachable(env_base_url: str) -> None:
    """Fail fast for wrong host/port instead of silently writing zero scores."""
    health_url = f"{env_base_url.rstrip('/')}/health"
    try:
        response = httpx.get(health_url, timeout=10.0)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Cannot reach financial environment at {health_url}. "
            "Start the server or set FINANCIAL_ENV_BASE_URL."
        ) from exc


def _json_extract(text: str) -> Dict[str, Any] | None:
    # First try as-is.
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    # Try extracting outermost JSON object.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        # If no closing brace exists, try from first opening brace to end.
        start = text.find("{")
        if start == -1:
            return None
        candidate = text[start:]
    else:
        candidate = match.group(0)

    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    # Try repairing truncated JSON by balancing brackets and braces.
    open_braces = candidate.count("{") - candidate.count("}")
    open_brackets = candidate.count("[") - candidate.count("]")
    repaired = candidate + ("]" * max(0, open_brackets)) + ("}" * max(0, open_braces))
    try:
        parsed = json.loads(repaired)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _heuristic_action(observation: Dict[str, Any], task_name: str) -> FinancialAction:
    content = observation["content"]

    if task_name == "anomaly_classification":
        rows: List[Dict[str, Any]] = []
        tx_line_pattern = re.compile(r"^TX-\d{3}-\d{2}")
        for line in content.splitlines():
            text = line.strip()
            if not tx_line_pattern.match(text):
                continue

            if "|" in text:
                parts = [part.strip() for part in text.split("|")]
            else:
                csv_parts = [part.strip() for part in text.split(",")]
                # CSV rows include amounts like "USD 4,999.00", so naive comma split
                # produces 7 tokens. Rejoin amount tail back into a single field.
                if len(csv_parts) >= 6:
                    head = csv_parts[:5]
                    amount_tail = ",".join(csv_parts[5:]).strip()
                    parts = head + [amount_tail]
                else:
                    parts = csv_parts

            if len(parts) < 6:
                continue

            amount_match = re.search(r"([\d,]+\.\d+)$", parts[5])
            if not amount_match:
                continue

            try:
                timestamp = datetime.strptime(parts[1], "%Y-%m-%d %H:%M")
                amount = float(amount_match.group(1).replace(",", ""))
            except ValueError:
                continue

            rows.append(
                {
                    "id": parts[0],
                    "timestamp": timestamp,
                    "counterparty": parts[3],
                    "vendor_category": parts[4],
                    "amount": amount,
                }
            )

        selected: List[str] = []

        # Near-duplicate: same vendor, close timestamp, amount nearly equal.
        for i in range(len(rows) - 1):
            left = rows[i]
            right = rows[i + 1]
            if (
                left["counterparty"] == right["counterparty"]
                and abs((right["timestamp"] - left["timestamp"]).total_seconds()) <= 90 * 60
                and abs(float(right["amount"]) - float(left["amount"])) <= 1.0
            ):
                selected.append(str(right["id"]))
                break

        threshold_rows = [
            row for row in rows if abs(float(row["amount"]) - 4999.0) < 0.01
        ]
        for row in threshold_rows[:2]:
            selected.append(str(row["id"]))

        oakline_rows = [
            row for row in rows if row["counterparty"].lower() == "oakline transport"
        ]
        oakline_rows.sort(key=lambda item: item["timestamp"])
        for i in range(len(oakline_rows) - 2):
            window = oakline_rows[i : i + 3]
            elapsed = (window[-1]["timestamp"] - window[0]["timestamp"]).total_seconds()
            if elapsed <= 2 * 60 * 60:
                selected.append(str(window[-1]["id"]))
                break

        office_mismatch = [
            row
            for row in rows
            if row["vendor_category"] == "office_supplies" and float(row["amount"]) > 5000
        ]
        if office_mismatch:
            selected.append(str(office_mismatch[0]["id"]))

        unique_ids = list(dict.fromkeys(selected))[:6]
        values = ",".join(unique_ids)
        return FinancialAction(
            action_type="classify",
            value=values,
            confidence=0.55,
            reasoning="Heuristic fallback selected pattern-based anomaly IDs.",
        )

    if task_name == "kpi_extraction":
        def _extract_amount(pattern: str) -> float | None:
            match = re.search(pattern, content, re.IGNORECASE)
            if not match:
                return None
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                return None

        revenue = _extract_amount(r"Revenue control total \(USD actual\).*?USD\s+([\d,]+\.\d+)")
        gross_profit = _extract_amount(r"Gross Profit control total \(USD actual\).*?USD\s+([\d,]+\.\d+)")

        operating_income_k = _extract_amount(r"Operating income\.*\s+USD\s+([\d,]+\.\d+)")
        dep_k = _extract_amount(r"Depreciation expense\.*\s+USD\s+([\d,]+\.\d+)")
        amort_k = _extract_amount(r"Amortization of intangibles\.*\s+USD\s+([\d,]+\.\d+)")
        addback_k = _extract_amount(r"Restructuring add-back\.*\s+USD\s+([\d,]+\.\d+)")
        net_income_k = _extract_amount(r"Net earnings attributable\.*\s+USD\s+([\d,]+\.\d+)")

        if all(val is not None for val in [operating_income_k, dep_k, amort_k, addback_k]):
            ebitda = (operating_income_k + dep_k + amort_k + addback_k) * 1000.0  # type: ignore[operator]
        else:
            ebitda = 0.0

        net_income = (net_income_k * 1000.0) if net_income_k is not None else 0.0

        kpis = {
            "revenue": revenue if revenue is not None else 0.0,
            "gross_profit": gross_profit if gross_profit is not None else 0.0,
            "net_income": net_income,
            "ebitda": ebitda,
        }
        return FinancialAction(
            action_type="extract_kpi",
            value=json.dumps(kpis),
            confidence=0.72,
            reasoning="Heuristic fallback extracted restated control totals and derived EBITDA from bridge lines.",
        )

    issues: List[Dict[str, str]] = []
    if "covenant" in content.lower():
        issues.append(
            {
                "type": "debt_covenant_breach_risk",
                "severity": "high",
                "description": "Detected covenant pressure note.",
            }
        )
    if "affiliate" in content.lower():
        issues.append(
            {
                "type": "related_party_transactions",
                "severity": "medium",
                "description": "Detected affiliate procurement signal.",
            }
        )
    if "cut-off" in content.lower() or "revenue" in content.lower():
        issues.append(
            {
                "type": "revenue_recognition_irregularity",
                "severity": "high",
                "description": "Detected revenue timing language.",
            }
        )

    return FinancialAction(
        action_type="flag_issue",
        value=json.dumps({"issues": issues}),
        confidence=0.5,
        reasoning="Heuristic fallback used rule-based compliance flags.",
    )


def _build_prompt_easy(observation: Dict[str, Any]) -> str:
    return (
        "You are a financial anomaly triage agent.\n"
        "Output MUST be a single strict JSON object with fields: action_type, value, confidence, reasoning.\n"
        "No markdown and no text outside JSON.\n\n"
        "Set action_type to classify.\n"
        "Return ONLY a comma-separated list of transaction IDs in value, exactly as they appear in tx_id.\n"
        "Example valid format: TX-042-03,TX-042-11,TX-042-19\n"
        "No spaces around commas. No other text. Just the IDs.\n"
        "Worked mini-example output for value: TX-001-04,TX-001-09,TX-001-15,TX-001-22\n\n"
        "MAXIMUM 6 IDs total. If you identify more than 6 suspicious transactions,\n"
        "return only the 6 most confidently anomalous ones.\n"
        "Each anomaly pattern should contribute at most 1-2 IDs:\n"
        "- Near-duplicate: return only the second transaction when two adjacent rows have same counterparty and almost-equal amount\n"
        "- Threshold hugging: return only IDs where amount is EXACTLY 4999.00\n"
        "- Velocity cluster: return only the LAST of the 3 rapid transactions\n"
        "  for Oakline Transport within 2 hours\n"
        "- Category mismatch: return only the ID where office_supplies amount > 5000\n\n"
        "Look for these specific anomaly patterns:\n"
        "- Near-duplicate: same vendor, amounts differ by less than $1.00, close timestamps\n"
        "- Threshold hugging: amount is exactly $4,999.00 from the same vendor multiple times\n"
        "- Velocity cluster: same vendor (Oakline Transport) with 3 transactions within 2 hours\n"
        "- Category mismatch: vendor_category is office_supplies but amount exceeds $5,000\n\n"
        "Important: do not over-flag unusual-but-valid transactions.\n"
        "Task description:\n"
        f"{observation['task_description']}\n"
        "Document:\n"
        f"{observation['content']}\n"
    )


def _fallback_parse_action(task_name: str) -> FinancialAction:
    if task_name == "anomaly_classification":
        return FinancialAction(
            action_type="classify",
            value="",
            confidence=0.0,
            reasoning="Fallback due to parse failure.",
        )
    if task_name == "kpi_extraction":
        return FinancialAction(
            action_type="extract_kpi",
            value='{"revenue":0.0,"gross_profit":0.0,"net_income":0.0,"ebitda":0.0}',
            confidence=0.0,
            reasoning="Fallback due to parse failure.",
        )
    return FinancialAction(
        action_type="flag_issue",
        value='{"issues":[]}',
        confidence=0.0,
        reasoning="Fallback due to parse failure.",
    )


def _build_prompt_medium(observation: Dict[str, Any]) -> str:
    return (
        "You are a financial KPI extraction agent.\n"
        "Output MUST be a single strict JSON object with fields: action_type, value, confidence, reasoning.\n"
        "No markdown and no text outside JSON.\n\n"
        "Set action_type to extract_kpi.\n"
        "Set value to a raw JSON string exactly in this shape:\n"
        '{"revenue": 3450000.0, "gross_profit": 1200000.0, "net_income": 450000.0, "ebitda": 780000.0}\n'
        "Values must be full USD amounts (not thousands). Plain floats only.\n\n"
        "CRITICAL: Use ONLY the lines labeled 'control total (USD actual)' for revenue and gross_profit.\n"
        "These are already in full USD. Do NOT use comparative table values in thousands.\n\n"
        "For ebitda: in 'Operating performance bridge', sum:\n"
        "Operating income + Depreciation expense + Amortization of intangibles + Restructuring add-back.\n"
        "Those four are in USD thousands, so multiply the sum by 1000.\n\n"
        "For net_income: use 'Net earnings attributable'.\n"
        "That line is in USD thousands, so multiply by 1000.\n\n"
        "Use FY2023 Restated values when both original and restated are shown.\n"
        "Task description:\n"
        f"{observation['task_description']}\n"
        "Document:\n"
        f"{observation['content']}\n"
    )


def _build_prompt_hard(observation: Dict[str, Any]) -> str:
    return (
        "You are a compliance risk assessment agent.\n"
        "Output MUST be a single strict JSON object with fields: action_type, value, confidence, reasoning.\n"
        "No markdown and no text outside JSON.\n\n"
        "Set action_type to flag_issue.\n"
        "Set value to a raw JSON string with this schema:\n"
        '{"issues": [{"type": "issue_slug", "severity": "low|medium|high", "description": "brief"}]}\n\n'
        "DO NOT flag items the document explicitly states are disclosed, approved, benchmarked, or temporary.\n"
        "These are red herrings and will penalize your score.\n\n"
        "YOUR RESPONSE WILL SCORE ZERO FOR ANY ISSUE TYPE NOT IN THIS EXACT LIST.\n"
        "Copy-paste the type field from this list only, no variations:\n\n"
        "debt_covenant_breach_risk\n"
        "related_party_transactions\n"
        "revenue_recognition_irregularity\n"
        "inventory_valuation_concern\n"
        "liquidity_deterioration_trend\n"
        "cash_flow_debt_mismatch\n"
        "hedged_disclosure_weakness\n"
        "contingent_liability_understatement\n"
        "off_balance_sheet_commitment\n"
        "tax_provision_uncertainty\n"
        "goodwill_impairment_delay\n"
        "going_concern_signal\n\n"
        "For severity use exactly: high, medium, or low (lowercase only).\n"
        "Flag between 3 and 6 issues maximum.\n"
        "Do not flag red herrings. Items the document says are disclosed, approved, benchmarked,\n"
        "or temporary score -0.15 each if flagged.\n\n"
        "CRITICAL LENGTH LIMIT: Your entire JSON value string must be under 700 characters.\n"
        "Keep each description to 5 words maximum.\n"
        "Good: 'Net debt exceeds covenant threshold'\n"
        "Bad: 'Net debt/EBITDA exceeds 3.5x covenant threshold in FY2025 based on analysis'\n"
        "With 4 issues at 5 words each, you will stay within the limit.\n\n"
        "Few-shot output format example for value:\n"
        '{"issues": ['
        '{"type": "debt_covenant_breach_risk", "severity": "high", '
        '"description": "Net debt/EBITDA exceeds 3.5x covenant threshold in FY2025"}, '
        '{"type": "going_concern_signal", "severity": "high", '
        '"description": "Refinancing not contractually secured despite liquidity dependency"}'
        ']}\n'
        "Task description:\n"
        f"{observation['task_description']}\n"
        "Document:\n"
        f"{observation['content']}\n"
    )


def _build_prompt(observation: Dict[str, Any]) -> str:
    difficulty = observation["task_difficulty"]
    if difficulty == "easy":
        return _build_prompt_easy(observation)
    if difficulty == "medium":
        return _build_prompt_medium(observation)
    return _build_prompt_hard(observation)


def _llm_action(
    llm_client: OpenAI,
    model_name: str,
    observation: Dict[str, Any],
) -> tuple[str, FinancialAction | None]:
    prompt = _build_prompt(observation)
    difficulty = observation.get("task_difficulty", "easy")
    max_tokens = 1200 if difficulty == "hard" else 600

    try:
        response = llm_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You output strict JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=max_tokens,
        )
    except Exception:  # noqa: BLE001
        return "api_error", None

    content = response.choices[0].message.content or ""

    # If output appears truncated, try balancing brackets/braces before parse.
    if content and not content.rstrip().endswith(('"}', '"]', "}", "]")):
        trimmed = content.rstrip()
        open_braces = trimmed.count("{") - trimmed.count("}")
        open_brackets = trimmed.count("[") - trimmed.count("]")
        content = trimmed + ("]" * max(0, open_brackets)) + ("}" * max(0, open_braces))

    parsed = _json_extract(content)
    if not parsed:
        return "parse_error", None

    # Models often return value as a JSON object instead of a JSON string.
    # Coerce it so FinancialAction validation stays robust.
    if isinstance(parsed.get("value"), (dict, list)):
        parsed["value"] = json.dumps(parsed["value"])

    try:
        return "success", FinancialAction.model_validate(parsed)
    except Exception:  # noqa: BLE001
        return "parse_error", None


def main() -> None:
    load_dotenv()

    def log_start(task, env_name, model):
        print(f"[START] task={task} env={env_name} model={model}", flush=True)

    def log_step(step, action, reward, done, error):
        error_val = error if error else "null"
        print(f"[STEP] step={step} action={action} reward={reward:.2f} done={str(done).lower()} error={error_val}", flush=True)

    def log_end(success, steps, score, rewards):
        rewards_str = ",".join(f"{r:.2f}" for r in rewards)
        print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)

    api_base_url = os.environ.get("API_BASE_URL", "https://api-inference.huggingface.co/v1")
    model_name = os.environ.get("MODEL_NAME", "meta-llama/Llama-3.1-8B-Instruct")
    # OpenAI-compatible client: official key or HF Inference token (hackathon / Spaces).
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("HF_TOKEN", "")
    env_base_url = os.environ.get("FINANCIAL_ENV_BASE_URL", "http://localhost:7860")
    env_max_steps = max(1, int(os.environ.get("FINANCIAL_ENV_MAX_STEPS", "1")))

    _assert_env_is_reachable(env_base_url)

    llm_client = OpenAI(base_url=api_base_url, api_key=api_key)
    env = FinancialDocEnv(base_url=env_base_url)

    raw_scores: Dict[str, List[float]] = {
        "task_easy": [],
        "task_medium": [],
        "task_hard": [],
    }

    for task_name in ["anomaly_classification", "kpi_extraction", "compliance_assessment"]:
        key = TASK_TO_KEY[task_name]
        for _ in range(5):
            log_start(task_name, "finsight", model_name)

            error = None
            done = False
            reward = 0.0
            step_rewards: List[float] = []
            action_type = "recommend"
            episode_score = 0.0

            try:
                observation = env.reset(task_name=task_name, max_steps=env_max_steps)
                max_rollout_steps = int(observation.get("max_steps", env_max_steps) or env_max_steps)

                for step_idx in range(1, max_rollout_steps + 1):
                    status, action = _llm_action(llm_client, model_name, observation)
                    if status == "parse_error":
                        action = _fallback_parse_action(task_name)
                    elif action is None:
                        action = _heuristic_action(observation, task_name)

                    action_type = action.action_type
                    result = env.step(action)
                    reward_value = result.get("reward")
                    reward = float(reward_value) if isinstance(reward_value, (int, float)) else 0.0
                    reward = _bounded_score(reward)
                    step_rewards.append(reward)
                    done = bool(result.get("done", False))
                    log_step(step_idx, action_type, reward, done, None)

                    observation = result
                    if done:
                        running_score = result.get("running_score")
                        episode_score = float(running_score) if isinstance(running_score, (int, float)) else reward
                        break

                if not done:
                    # In case the API returns non-terminal unexpectedly, use mean reward so far.
                    episode_score = mean(step_rewards) if step_rewards else 0.0
            except Exception as exc:  # noqa: BLE001
                error = str(exc)
                log_step(1, action_type, reward, done, error)

            score = _bounded_score(episode_score)
            success = error is None and score >= 0.5
            raw_scores[key].append(score)
            log_end(success, len(step_rewards) if step_rewards else 1, score, step_rewards)

    results = {
        "task_easy": {"mean": mean(raw_scores["task_easy"]) if raw_scores["task_easy"] else 0.0, "scores": raw_scores["task_easy"]},
        "task_medium": {
            "mean": mean(raw_scores["task_medium"]) if raw_scores["task_medium"] else 0.0,
            "scores": raw_scores["task_medium"],
        },
        "task_hard": {"mean": mean(raw_scores["task_hard"]) if raw_scores["task_hard"] else 0.0, "scores": raw_scores["task_hard"]},
    }

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
 