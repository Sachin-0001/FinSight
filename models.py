from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Field sets align with openenv.core.env_server.types Action / Observation (done, reward, metadata).


class FinancialAction(BaseModel):
    """Agent action: structured answer plus calibration and rationale."""

    action_type: str = Field(
        ...,
        description='Task-specific: "classify", "extract_kpi", or "flag_issue" (see observation.legal_actions).',
    )
    value: str = Field(..., description="Agent answer payload as plain text or JSON string")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., min_length=1)
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional extras (OpenEnv Action-compatible)",
    )


class FinancialReward(BaseModel):
    """Decomposed reward in [0, 1] (shaped signal + grader root)."""

    value: float = Field(..., ge=0.0, le=1.0, description="Final shaped reward after clamping")
    grader_score: float = Field(..., ge=0.0, le=1.0, description="Task grader output before shaping")
    confidence_bonus: float = Field(0.0, description="Calibration bonus when confidence matches grader")
    illegal_action_penalty: float = Field(0.0, le=0.0, description="Penalty when action_type ∉ legal_actions")
    step_efficiency_penalty: float = Field(0.0, le=0.0, description="Penalty for extra steps in multi-step episodes")


class FinancialObservation(BaseModel):
    """Observation: document, task spec, progress, terminal flags (OpenEnv Observation-compatible)."""

    document_id: str
    document_type: Literal["income_statement", "balance_sheet", "transaction_log"]
    content: str
    task_description: str
    task_difficulty: Literal["easy", "medium", "hard"]
    legal_actions: List[str]
    step_in_episode: int
    max_steps: int
    running_score: float
    done: bool = False
    reward: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FinancialState(BaseModel):
    """Session-level statistics for the active or last-completed episode."""

    episode_id: str
    task_name: str
    task_difficulty: str
    step_count: int
    total_score: float
    max_possible_score: float
    documents_processed: int


__all__ = [
    "FinancialAction",
    "FinancialObservation",
    "FinancialReward",
    "FinancialState",
]
