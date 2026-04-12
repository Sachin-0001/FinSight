from __future__ import annotations
import os
import time
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from models import FinancialAction, FinancialState
from server.environment import FinancialDocEnvironment


class ResetRequest(BaseModel):
    task_name: Optional[str] = None
    difficulty: Optional[str] = None
    max_steps: Optional[int] = None


class StepRequest(BaseModel):
    episode_id: Optional[str] = None
    task_name: Optional[str] = None
    episode_seed: Optional[int] = None
    action: FinancialAction


class EpisodeStateRequest(BaseModel):
    """Optional body for POST /state: when episode_id is set, return that episode's FinancialState."""

    episode_id: Optional[str] = None


def _attach_step_info(payload: Dict[str, Any]) -> Dict[str, Any]:
    """OpenEnv-style ``info`` alongside the flat observation JSON."""
    meta = payload.get("metadata") or {}
    rb = meta.get("reward_breakdown")
    payload["info"] = {
        "reward_breakdown": rb,
        "episode_phase": meta.get("episode_phase"),
        "running_score": payload.get("running_score"),
    }
    return payload


app = FastAPI(title="Financial Document OpenEnv")

_EPISODES: Dict[str, FinancialDocEnvironment] = {}
_EPISODE_TTL_SECONDS = 30 * 60
_EPISODE_LAST_TOUCH: Dict[str, float] = {}


def _cleanup_stale_episodes() -> None:
    now = time.time()
    stale_ids = [
        eid for eid, touched in _EPISODE_LAST_TOUCH.items() if (now - touched) > _EPISODE_TTL_SECONDS
    ]
    for eid in stale_ids:
        _EPISODE_LAST_TOUCH.pop(eid, None)
        _EPISODES.pop(eid, None)


@app.post("/reset")
def reset_environment(payload: ResetRequest = None) -> Dict[str, Any]:
    if payload is None:
        payload = ResetRequest()
    try:
        _cleanup_stale_episodes()
        requested_max_steps = payload.max_steps if payload.max_steps is not None else 1
        env = FinancialDocEnvironment(max_steps=max(1, requested_max_steps))
        obs = env.reset(task_name=payload.task_name, difficulty=payload.difficulty)
        data = obs.model_dump()
        # Expose seed for backward-compatible stateless replay and track stateful episode.
        data["metadata"]["episode_seed"] = env.last_episode_seed
        _EPISODES[env.episode_id] = env
        _EPISODE_LAST_TOUCH[env.episode_id] = time.time()
        return _attach_step_info(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/step")
def step_environment(payload: StepRequest) -> Dict[str, Any]:
    try:
        _cleanup_stale_episodes()

        # Preferred mode: stateful stepping using episode_id.
        if payload.episode_id:
            env = _EPISODES.get(payload.episode_id)
            if env is None:
                raise ValueError(f"Unknown or expired episode_id: {payload.episode_id}")
            _EPISODE_LAST_TOUCH[payload.episode_id] = time.time()
            obs = env.step(payload.action)
            data = obs.model_dump()
            if obs.done:
                _EPISODES.pop(payload.episode_id, None)
                _EPISODE_LAST_TOUCH.pop(payload.episode_id, None)
            return _attach_step_info(data)

        # Backward-compatible mode: stateless replay with task_name + episode_seed.
        if not payload.task_name or payload.episode_seed is None:
            raise ValueError("Provide episode_id (preferred) or both task_name and episode_seed.")

        env = FinancialDocEnvironment(max_steps=1)
        env.force_episode_seed(payload.episode_seed)
        env.reset(task_name=payload.task_name)
        obs = env.step(payload.action)
        return _attach_step_info(obs.model_dump())
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
    """Deployment / catalog metadata (introspection)."""
    _cleanup_stale_episodes()
    return {
        "environment": "financial-doc-env",
        "version": "1.0.0",
        "tasks": ["anomaly_classification", "kpi_extraction", "compliance_assessment"],
        "status": "ready",
        "api_mode": "stateful-http-with-backward-compat",
        "episode_tracking": "prefer reset metadata.episode_id with /step",
        "active_episodes": len(_EPISODES),
    }


@app.post("/state")
def post_episode_state(payload: Optional[EpisodeStateRequest] = None) -> Dict[str, Any]:
    """Return ``FinancialState`` for an active episode (OpenEnv-style state query)."""
    _cleanup_stale_episodes()
    if payload is None:
        payload = EpisodeStateRequest()
    if not payload.episode_id:
        raise HTTPException(
            status_code=400,
            detail="Provide episode_id in JSON body (from reset metadata).",
        )
    env = _EPISODES.get(payload.episode_id)
    if env is None:
        raise HTTPException(status_code=404, detail=f"Unknown or expired episode_id: {payload.episode_id}")
    _EPISODE_LAST_TOUCH[payload.episode_id] = time.time()
    st: FinancialState = env.state
    return st.model_dump()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    env = FinancialDocEnvironment(max_steps=1)
    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")
            if msg_type == "reset":
                try:
                    max_steps = int(message.get("max_steps", 1) or 1)
                    env = FinancialDocEnvironment(max_steps=max(1, max_steps))
                    obs = env.reset(
                        task_name=message.get("task_name"),
                        difficulty=message.get("difficulty"),
                    )
                    _EPISODES[env.episode_id] = env
                    _EPISODE_LAST_TOUCH[env.episode_id] = time.time()
                    await websocket.send_json({"type": "observation", "data": _attach_step_info(obs.model_dump())})
                except ValueError as exc:
                    await websocket.send_json({"type": "error", "error": str(exc)})
            elif msg_type == "state":
                eid = message.get("episode_id")
                if eid is None or (isinstance(eid, str) and eid == env.episode_id):
                    await websocket.send_json({"type": "state", "data": env.state.model_dump()})
                    continue
                if not isinstance(eid, str):
                    await websocket.send_json({"type": "error", "error": "Invalid episode_id for state"})
                    continue
                target = _EPISODES.get(eid)
                if target is None:
                    await websocket.send_json({"type": "error", "error": f"Unknown episode_id: {eid}"})
                    continue
                _EPISODE_LAST_TOUCH[eid] = time.time()
                await websocket.send_json({"type": "state", "data": target.state.model_dump()})
            elif msg_type == "step":
                raw_action = message.get("action")
                if not isinstance(raw_action, dict):
                    await websocket.send_json({"type": "error", "error": "Missing or invalid 'action' payload"})
                    continue
                try:
                    action = FinancialAction.model_validate(raw_action)
                    obs = env.step(action)
                    if obs.done:
                        _EPISODES.pop(env.episode_id, None)
                        _EPISODE_LAST_TOUCH.pop(env.episode_id, None)
                    await websocket.send_json({"type": "observation", "data": _attach_step_info(obs.model_dump())})
                except Exception as exc:
                    await websocket.send_json({"type": "error", "error": str(exc)})
            else:
                await websocket.send_json({"type": "error", "error": "Unsupported message type."})
    except WebSocketDisconnect:
        _EPISODES.pop(env.episode_id, None)
        _EPISODE_LAST_TOUCH.pop(env.episode_id, None)
        return
    
def main():
      import uvicorn
      port = int(os.environ.get("PORT", 7860))
      uvicorn.run("server.app:app", host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()