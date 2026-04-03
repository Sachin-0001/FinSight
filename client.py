from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from models import FinancialAction, FinancialState

StepResult = Dict[str, Any]


class FinancialDocEnv:
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")
        self._pending_task: Optional[str] = None
        self._pending_seed: int = 0
        
    def reset(self, task_name=None, difficulty=None) -> StepResult:
        payload = {"task_name": task_name, "difficulty": difficulty}
        with httpx.Client(timeout=30.0) as client:
            response = client.post(f"{self.base_url}/reset", json=payload)
            response.raise_for_status()
            data = response.json()
            # cache seed and task for the upcoming step call
            self._pending_task = task_name
            self._pending_seed = data.get("metadata", {}).get("episode_seed", 0)
            return data

    def step(self, action: FinancialAction) -> StepResult:
        payload = {
            "task_name": self._pending_task,
            "episode_seed": self._pending_seed,
            "action": action.model_dump(),
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(f"{self.base_url}/step", json=payload)
            response.raise_for_status()
            return response.json()
        
    def step_with_task(self, task_name: str, action: FinancialAction) -> StepResult:
        payload = {"task_name": task_name, "action": action.model_dump()}
        with httpx.Client(timeout=30.0) as client:
            response = client.post(f"{self.base_url}/step", json=payload)
            response.raise_for_status()
        return response.json()

    def state(self) -> FinancialState:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{self.base_url}/state")
            response.raise_for_status()
            return FinancialState.model_validate(response.json())

    async def async_reset(
        self,
        task_name: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> StepResult:
        payload = {"task_name": task_name, "difficulty": difficulty}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/reset", json=payload)
            response.raise_for_status()
            return response.json()

    async def async_step(self, action: FinancialAction) -> StepResult:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/step", json=action.model_dump())
            response.raise_for_status()
            return response.json()

    async def async_state(self) -> FinancialState:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/state")
            response.raise_for_status()
            return FinancialState.model_validate(response.json())

    

    def sync(self) -> "FinancialDocEnv":
        return self
