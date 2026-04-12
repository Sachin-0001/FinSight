from __future__ import annotations

from dataclasses import dataclass
import os
from random import Random
from typing import Any, Dict, Optional
from uuid import uuid4

from models import FinancialAction, FinancialObservation, FinancialReward, FinancialState
from server.tasks import TASKS, TaskDefinition, generate_task_instance, grade_task


@dataclass
class EpisodeContext:
    task: TaskDefinition
    document_id: str
    document: str
    ground_truth: Dict[str, Any]


class FinancialDocEnvironment:
    def __init__(self, seed: Optional[int] = None, max_steps: int = 1) -> None:
        self._master_rng = Random(seed)
        self.max_steps = max_steps
        self.last_episode_seed: int = 0
        self._forced_episode_seed: Optional[int] = None
        self._rng = Random(seed)
        self.episode_id = ""
        self.task_name = ""
        self.task_difficulty = ""
        self.step_count = 0
        self.total_score = 0.0
        self.max_possible_score = 0.0
        self.documents_processed = 0

        self._episode: Optional[EpisodeContext] = None
        self._done = False
        self._running_score = 0.0
        self._episode_reward_sum = 0.0

    def force_episode_seed(self, seed: int) -> None:
        """Call this before reset() to pin the exact episode seed."""
        self._forced_episode_seed = seed

    def _bound_score(self, score: float) -> float:
        """Ensure score is between 0 and 1 (inclusive)."""
        return max(0.0, min(1.0, score))

    def _include_debug_metadata(self) -> bool:
        return os.getenv("FINANCIAL_ENV_DEBUG_METADATA", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _pick_task(self, task_name: Optional[str], difficulty: Optional[str]) -> str:
        if task_name:
            if task_name not in TASKS:
                raise ValueError(f"Unknown task_name: {task_name}")
            return task_name
        if difficulty:
            candidates = [name for name, task in TASKS.items() if task.difficulty == difficulty]
            if not candidates:
                raise ValueError(f"Unknown difficulty: {difficulty}")
            return candidates[self._rng.randrange(0, len(candidates))]
        keys = list(TASKS.keys())
        return keys[self._rng.randrange(0, len(keys))]

    def reset(self, task_name: Optional[str] = None, difficulty: Optional[str] = None) -> FinancialObservation:
        selected_task = self._pick_task(task_name=task_name, difficulty=difficulty)
        if self._forced_episode_seed is not None:
            seed = self._forced_episode_seed
            self._forced_episode_seed = None
        else:
            seed = self._master_rng.randint(1, 10_000_000)
        self.last_episode_seed = seed
        generated = generate_task_instance(selected_task, seed=seed)
        task: TaskDefinition = generated["task"]

        self.episode_id = str(uuid4())
        self.task_name = task.name
        self.task_difficulty = task.difficulty
        self.step_count = 0
        self._running_score = 0.0
        self._episode_reward_sum = 0.0
        self._done = False
        # One point at stake for the current episode; do not increment on abandoned resets.
        self.max_possible_score = float(self.documents_processed + 1)

        self._episode = EpisodeContext(
            task=task,
            document_id=f"DOC-{seed}-{task.name}",
            document=generated["document"],
            ground_truth=generated["ground_truth"],
        )

        return FinancialObservation(
            document_id=self._episode.document_id,
            document_type=task.document_type,
            content=self._episode.document,
            task_description=task.description,
            task_difficulty=task.difficulty,
            legal_actions=task.legal_actions,
            step_in_episode=self.step_count,
            max_steps=self.max_steps,
            running_score=self._running_score,
            done=False,
            reward=None,
            metadata={
                "task_name": task.name,
                "episode_id": self.episode_id,
                "reward_breakdown": None,
                "episode_phase": "awaiting_action",
            },
        )

    def step(self, action: FinancialAction) -> FinancialObservation:
        if self._episode is None:
            raise RuntimeError("Call reset() before step().")

        if self._done:
            return FinancialObservation(
                document_id=self._episode.document_id,
                document_type=self._episode.task.document_type,
                content=self._episode.document,
                task_description=self._episode.task.description,
                task_difficulty=self._episode.task.difficulty,
                legal_actions=self._episode.task.legal_actions,
                step_in_episode=self.step_count,
                max_steps=self.max_steps,
                running_score=self._running_score,
                done=True,
                reward=0.0,
                metadata={
                    "task_name": self._episode.task.name,
                    "episode_id": self.episode_id,
                    "reward_breakdown": None,
                    "episode_phase": "terminal",
                },
            )

        self.step_count += 1

        grader_score = self._bound_score(
            grade_task(self._episode.task.name, action, self._episode.ground_truth)
        )
        confidence_bonus = 0.1 if abs(action.confidence - grader_score) < 0.15 else 0.0
        illegal_penalty = -0.2 if action.action_type not in self._episode.task.legal_actions else 0.0
        step_penalty = -0.1 * (self.step_count - 1) if self.step_count > 1 else 0.0
        pre_clamp = grader_score + confidence_bonus + illegal_penalty + step_penalty
        reward = self._bound_score(pre_clamp)

        reward_model = FinancialReward(
            value=reward,
            grader_score=grader_score,
            confidence_bonus=confidence_bonus,
            illegal_action_penalty=illegal_penalty,
            step_efficiency_penalty=step_penalty,
        )
        reward_breakdown = reward_model.model_dump()

        self._episode_reward_sum += reward
        self._running_score = self._episode_reward_sum / self.step_count
        self._done = self.step_count >= self.max_steps

        metadata: Dict[str, Any] = {
            "task_name": self._episode.task.name,
            "episode_id": self.episode_id,
            "reward_breakdown": reward_breakdown,
            "episode_phase": "complete" if self._done else "in_progress",
        }
        if self._include_debug_metadata():
            metadata["ground_truth"] = self._episode.ground_truth

        if self._done:
            self.total_score += self._running_score
            self.documents_processed += 1

        return FinancialObservation(
            document_id=self._episode.document_id,
            document_type=self._episode.task.document_type,
            content=self._episode.document,
            task_description=self._episode.task.description,
            task_difficulty=self._episode.task.difficulty,
            legal_actions=self._episode.task.legal_actions,
            step_in_episode=self.step_count,
            max_steps=self.max_steps,
            running_score=self._running_score,
            done=self._done,
            reward=reward,
            metadata=metadata,
        )

    @property
    def state(self) -> FinancialState:
        return FinancialState(
            episode_id=self.episode_id,
            task_name=self.task_name,
            task_difficulty=self.task_difficulty,
            step_count=self.step_count,
            total_score=self.total_score,
            max_possible_score=self.max_possible_score,
            documents_processed=self.documents_processed,
        )
