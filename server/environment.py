from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Any, Dict, Optional
from uuid import uuid4

from models import FinancialAction, FinancialObservation, FinancialState
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

    def force_episode_seed(self, seed: int) -> None:
        """Call this before reset() to pin the exact episode seed."""
        self._forced_episode_seed = seed

    def _clamp_score(self, score: float) -> float:
        """Ensure score is strictly between 0 and 1 (exclusive)."""
        return max(0.001, min(0.999, score))

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
        self._done = False
        self.max_possible_score += 1.0

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
            metadata={"task_name": task.name, "episode_id": self.episode_id},
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
                reward=self._clamp_score(0.0),
                metadata={"task_name": self._episode.task.name, "episode_id": self.episode_id},
            )

        self.step_count += 1

        grader_score = grade_task(self._episode.task.name, action, self._episode.ground_truth)
        reward = grader_score

        if abs(action.confidence - grader_score) < 0.15:
            reward += 0.1
        if action.action_type not in self._episode.task.legal_actions:
            reward -= 0.2
        if self.step_count > 1:
            reward -= 0.1 * (self.step_count - 1)

        reward = self._clamp_score(reward)
        self._running_score = reward
        self.total_score += reward
        self.documents_processed += 1
        self._done = True

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
            reward=reward,
            metadata={
                "task_name": self._episode.task.name,
                "episode_id": self.episode_id,
                "grader_score": grader_score,
                "ground_truth": self._episode.ground_truth,
            },
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
