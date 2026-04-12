from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx

from models import FinancialAction

StepResult = Dict[str, Any]


class FinancialDocEnv:
    def __init__(self, base_url: Optional[str] = None) -> None:
        resolved_base_url = base_url or os.environ.get("FINANCIAL_ENV_BASE_URL", "http://localhost:7860")
        self.base_url = resolved_base_url.rstrip("/")
        self._pending_task: Optional[str] = None
        self._pending_seed: int = 0
        self._pending_episode_id: Optional[str] = None
        
    def reset(self, task_name=None, difficulty=None, max_steps: Optional[int] = None) -> StepResult:
        payload = {"task_name": task_name, "difficulty": difficulty, "max_steps": max_steps}
        with httpx.Client(timeout=30.0) as client:
            response = client.post(f"{self.base_url}/reset", json=payload)
            response.raise_for_status()
            data = response.json()
            metadata = data.get("metadata", {})
            self._pending_task = metadata.get("task_name") or task_name
            self._pending_seed = int(metadata.get("episode_seed") or 0)
            self._pending_episode_id = metadata.get("episode_id")
            return data

    def step(self, action: FinancialAction) -> StepResult:
        if not self._pending_episode_id and (not self._pending_task or self._pending_seed <= 0):
            raise RuntimeError("Call reset() and use returned episode before step().")
        payload = {
            "episode_id": self._pending_episode_id,
            "task_name": self._pending_task,
            "episode_seed": self._pending_seed,
            "action": action.model_dump(),
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(f"{self.base_url}/step", json=payload)
            response.raise_for_status()
            data = response.json()
            if bool(data.get("done", False)):
                self._pending_episode_id = None
            return data
        
    def step_with_task(self, task_name: str, action: FinancialAction) -> StepResult:
        self.reset(task_name=task_name)
        return self.step(action)

    def state(self) -> Dict[str, Any]:
        """Server catalog / deployment metadata (GET /state)."""
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{self.base_url}/state")
            response.raise_for_status()
            return response.json()

    def episode_state(self) -> Dict[str, Any]:
        """FinancialState for the current episode (POST /state); call after reset()."""
        if not self._pending_episode_id:
            raise RuntimeError("Call reset() first; episode_id comes from observation metadata.")
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.base_url}/state",
                json={"episode_id": self._pending_episode_id},
            )
            response.raise_for_status()
            return response.json()

    async def async_reset(
        self,
        task_name: Optional[str] = None,
        difficulty: Optional[str] = None,
        max_steps: Optional[int] = None,
    ) -> StepResult:
        payload = {"task_name": task_name, "difficulty": difficulty, "max_steps": max_steps}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/reset", json=payload)
            response.raise_for_status()
            data = response.json()
            metadata = data.get("metadata", {})
            self._pending_task = metadata.get("task_name") or task_name
            self._pending_seed = int(metadata.get("episode_seed") or 0)
            self._pending_episode_id = metadata.get("episode_id")
            return data

    async def async_step(self, action: FinancialAction) -> StepResult:
        if not self._pending_episode_id and (not self._pending_task or self._pending_seed <= 0):
            raise RuntimeError("Call async_reset() and use returned episode before async_step().")
        payload = {
            "episode_id": self._pending_episode_id,
            "task_name": self._pending_task,
            "episode_seed": self._pending_seed,
            "action": action.model_dump(),
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/step", json=payload)
            response.raise_for_status()
            data = response.json()
            if bool(data.get("done", False)):
                self._pending_episode_id = None
            return data

    async def async_state(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/state")
            response.raise_for_status()
            return response.json()

    

    def sync(self) -> "FinancialDocEnv":
        return self
