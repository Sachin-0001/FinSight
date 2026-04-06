from __future__ import annotations
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from models import FinancialAction
from server.environment import FinancialDocEnvironment


class ResetRequest(BaseModel):
    task_name: Optional[str] = None
    difficulty: Optional[str] = None


class StepRequest(BaseModel):
    task_name: str
    episode_seed: int        # ← seed returned by /reset, sent back by client
    action: FinancialAction


app = FastAPI(title="Financial Document OpenEnv")


@app.post("/reset")
def reset_environment(payload: ResetRequest) -> Dict[str, Any]:
    try:
        env = FinancialDocEnvironment()
        obs = env.reset(task_name=payload.task_name, difficulty=payload.difficulty)
        data = obs.model_dump()
        # expose the seed so /step can reproduce the exact same episode
        data["metadata"]["episode_seed"] = env.last_episode_seed
        return data
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/step")
def step_environment(payload: StepRequest) -> Dict[str, Any]:
    try:
        env = FinancialDocEnvironment()
        env.force_episode_seed(payload.episode_seed)
        env.reset(task_name=payload.task_name)
        obs = env.step(payload.action)
        return obs.model_dump()
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        import traceback
        raise HTTPException(status_code=500, detail=traceback.format_exc()) from exc


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "healthy", "environment": "financial-doc-env"}


@app.get("/state")
def get_state() -> Dict[str, Any]:
    return {
        "environment": "financial-doc-env",
        "version": "1.0.0",
        "tasks": ["anomaly_classification", "kpi_extraction", "compliance_assessment"],
        "status": "ready"
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    env = FinancialDocEnvironment()
    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")
            if msg_type == "reset":
                try:
                    obs = env.reset(
                        task_name=message.get("task_name"),
                        difficulty=message.get("difficulty"),
                    )
                    await websocket.send_json({"type": "observation", "data": obs.model_dump()})
                except ValueError as exc:
                    await websocket.send_json({"type": "error", "error": str(exc)})
            elif msg_type == "step":
                raw_action = message.get("action")
                if not isinstance(raw_action, dict):
                    await websocket.send_json({"type": "error", "error": "Missing or invalid 'action' payload"})
                    continue
                try:
                    action = FinancialAction.model_validate(raw_action)
                    obs = env.step(action)
                    await websocket.send_json({"type": "observation", "data": obs.model_dump()})
                except Exception as exc:
                    await websocket.send_json({"type": "error", "error": str(exc)})
            else:
                await websocket.send_json({"type": "error", "error": "Unsupported message type."})
    except WebSocketDisconnect:
        return