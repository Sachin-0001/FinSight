from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class FinancialAction(BaseModel):
    action_type: str = Field(
        ...,
        description='One of: "classify", "extract_kpi", "flag_issue", "recommend"',
    )
    value: str = Field(..., description="Agent answer payload as plain text or JSON string")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., min_length=1)


class FinancialObservation(BaseModel):
    document_id: str
    document_type: Literal["income_statement", "balance_sheet", "transaction_log"]
    content: str
    task_description: str
    task_difficulty: Literal["easy", "medium", "hard"]
    legal_actions: List[str]
    step_in_episode: int
    max_steps: int
    running_score: float
    done: bool
    reward: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FinancialState(BaseModel):
    episode_id: str
    task_name: str
    task_difficulty: str
    step_count: int
    total_score: float
    max_possible_score: float
    documents_processed: int
