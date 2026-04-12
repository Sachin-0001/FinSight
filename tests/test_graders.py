"""Determinism and bounds for task graders (no HTTP)."""

from __future__ import annotations

import pytest

from models import FinancialAction
from server.tasks import generate_task_instance, grade_task


def _action_classify(value: str, confidence: float = 0.9) -> FinancialAction:
    return FinancialAction(
        action_type="classify",
        value=value,
        confidence=confidence,
        reasoning="x" * 25,
    )


def _action_kpi(payload: str) -> FinancialAction:
    return FinancialAction(
        action_type="extract_kpi",
        value=payload,
        confidence=0.9,
        reasoning="x" * 25,
    )


def _action_compliance(payload: str) -> FinancialAction:
    return FinancialAction(
        action_type="flag_issue",
        value=payload,
        confidence=0.5,
        reasoning="x" * 25,
    )


@pytest.mark.parametrize("seed", [1, 2, 42, 99_001])
@pytest.mark.parametrize(
    "task",
    ["anomaly_classification", "kpi_extraction", "compliance_assessment"],
)
def test_grader_determinism(task: str, seed: int) -> None:
    g = generate_task_instance(task, seed=seed)
    gt = g["ground_truth"]
    if task == "anomaly_classification":
        a = _action_classify(",".join(gt["anomaly_ids"]))
    elif task == "kpi_extraction":
        import json

        body = {
            "revenue": gt["revenue"],
            "gross_profit": gt["gross_profit"],
            "net_income": gt["net_income"],
            "ebitda": gt["ebitda"],
        }
        a = _action_kpi(json.dumps(body))
    else:
        import json

        a = _action_compliance(json.dumps({"issues": gt["issues"]}))
    s1 = grade_task(task, a, gt)
    s2 = grade_task(task, a, gt)
    assert s1 == s2
    assert 0.0 <= s1 <= 1.0


def test_anomaly_perfect_f1_high(seed: int = 7) -> None:
    g = generate_task_instance("anomaly_classification", seed=seed)
    gt = g["ground_truth"]
    s = grade_task("anomaly_classification", _action_classify(",".join(gt["anomaly_ids"])), gt)
    assert s >= 0.85


def test_kpi_garbage_low() -> None:
    g = generate_task_instance("kpi_extraction", seed=11)
    gt = g["ground_truth"]
    s = grade_task("kpi_extraction", _action_kpi("{}"), gt)
    assert s < 0.5
