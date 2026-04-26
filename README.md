---
title: FinSight Financial Document OpenEnv
emoji: 📊
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
tags:
  - openenv
  - finance
  - reinforcement-learning
  - document-analysis
---

# Financial Document OpenEnv (FinSight)

## Motivation (real-world utility)

Financial operations teams spend large amounts of time on **transaction monitoring**, **management reporting (KPIs)**, and **disclosure / compliance review**. This environment turns those workflows into a **single Gym-style interface**: synthetic but structured documents, typed actions, **deterministic programmatic graders** (no LLM-as-judge), and **shaped rewards** so agents receive partial credit and penalties for miscalibration, illegal action types, and inefficient multi-step episodes.

## OpenEnv-style API (HTTP)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/reset` | Start an episode; returns initial observation (+ `metadata.episode_id`, `metadata.episode_seed`). |
| `POST` | `/step` | Submit a `FinancialAction`; returns observation, `reward`, `done`, and `info` (see below). |
| `POST` | `/state` | Body: `{"episode_id": "<id>"}` → `FinancialState` for an **active** episode. |
| `GET` | `/state` | Deployment catalog (task list, version, active episode count). |
| `GET` | `/health` | Liveness. |

**`info` field (step / reset responses):** mirrors partial-progress signal for learning and debugging:

- `reward_breakdown`: `FinancialReward` dict — `grader_score`, `confidence_bonus`, `illegal_action_penalty`, `step_efficiency_penalty`, `value` (final clamped reward).
- `episode_phase`: `awaiting_action` \| `in_progress` \| `complete` \| `terminal`.
- `running_score`: mean reward so far in the episode.

Set `FINANCIAL_ENV_DEBUG_METADATA=true` to include `ground_truth` in observation metadata (never use in production eval).

## Typed models (`models.py`)

- **`FinancialAction`** — `action_type`, `value`, `confidence`, `reasoning`, optional `metadata` (OpenEnv Action–compatible).
- **`FinancialObservation`** — document payload, task spec, `legal_actions`, `step_in_episode`, `max_steps`, `running_score`, `done`, `reward`, `metadata` (OpenEnv Observation–compatible).
- **`FinancialReward`** — explicit decomposition of the scalar reward in \([0,1]\).
- **`FinancialState`** — cumulative stats plus current episode id / task / step count.

## Observation space

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | `str` | Synthetic document id |
| `document_type` | `str` | `transaction_log`, `income_statement`, or `balance_sheet` |
| `content` | `str` | Full document text |
| `task_description` | `str` | Objective for this episode |
| `task_difficulty` | `str` | `easy` \| `medium` \| `hard` |
| `legal_actions` | `List[str]` | Allowed `action_type` values |
| `step_in_episode` | `int` | Steps taken |
| `max_steps` | `int` | Horizon (use `>1` for multi-step training) |
| `running_score` | `float` | Mean reward in the episode so far |
| `done` | `bool` | Terminal flag |
| `reward` | `float \| null` | Last step reward (null on initial reset) |
| `metadata` | `dict` | `episode_id`, `episode_seed`, `reward_breakdown`, etc. |

## Action space

| Field | Type | Description |
|-------|------|-------------|
| `action_type` | `str` | Must be one of `legal_actions` for the task |
| `value` | `str` | Comma-separated IDs, KPI JSON, or issues JSON |
| `confidence` | `float` | \([0,1]\); calibrated confidence vs grader feeds shaping |
| `reasoning` | `str` | Short rationale (quality heuristic in grader) |

## Tasks and graders

| Task | Difficulty | Objective | Grader |
|------|------------|-----------|--------|
| `anomaly_classification` | easy | List anomalous transaction IDs | F1 on id sets + quality heuristics |
| `kpi_extraction` | medium | JSON: revenue, gross_profit, net_income, ebitda | Per-KPI relative error bands + invalid JSON penalty |
| `compliance_assessment` | hard | JSON issues: type + severity slugs | Weighted detection + false-positive / red-herring penalties |

All task scores are **deterministic** given seed and action (see `tests/test_graders.py`).

## Reward shaping (meaningful signal)

1. **Grader score** in \([0,1]\) (partial credit per task).
2. **+0.1** if \(\lvert \text{confidence} - \text{grader\_score}\rvert < 0.15\) (calibration).
3. **−0.2** if `action_type` is not in `legal_actions`.
4. **−0.1 × (step − 1)** for extra steps when `max_steps > 1` (efficiency).
5. Final clamp to \([0,1]\). **`running_score`** is the mean of step rewards (trajectory signal over multiple steps).

## Setup

### Local

```bash
pip install -r requirements.txt
uvicorn server.app:app --host 0.0.0.0 --port 7860
```

### Docker

```bash
docker build -t financial-env .
docker run -p 7860:7860 financial-env
```

### Docker Compose (Backend + Frontend)

```bash
docker compose up --build
```

- Frontend UI: `http://localhost:8090`
- Backend API: `http://localhost:7861`

The frontend proxies backend calls via `/api` (for example, `/api/health`, `/api/state`, `/api/reset`).

### Minikube (Kubernetes, 3 replicas)

This repo includes a Minikube-ready manifest at `k8s/finsight-minikube.yaml` with:

- `backend` Deployment: **3 replicas**
- `frontend` Deployment: **3 replicas**
- `backend` ClusterIP Service on port `7860`
- `frontend` NodePort Service on port `30080`

Quick deploy:

```bash
./k8s/deploy_minikube.sh
```

Manual deploy:

```bash
minikube start
minikube image build -t finsight-backend:local .
minikube image build -t finsight-frontend:local ./frontend
kubectl apply -f k8s/finsight-minikube.yaml
kubectl get pods
minikube service frontend --url
```

Scale check:

```bash
kubectl get deploy backend frontend
```

Safe stop options:

```bash
# graceful stop (keeps Services/manifest)
./k8s/stop_minikube.sh

# full cleanup (delete all k8s objects from manifest)
./k8s/stop_minikube.sh --delete

# also stop minikube VM/container
./k8s/stop_minikube.sh --stop-minikube
```

### Terraform quick win (Kubernetes resources on Minikube)

This repo now includes Terraform config in `infra/terraform` to manage the same `backend` + `frontend` Deployments/Services currently defined in `k8s/finsight-minikube.yaml`.

Build local images for Minikube first:

```bash
minikube start
minikube image build -t finsight-backend:local .
minikube image build -t finsight-frontend:local ./frontend
```

Apply Terraform:

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply -auto-approve
```

Or use helper scripts:

```bash
./infra/start.sh
```

Verify and open service:

```bash
kubectl get deploy,svc
minikube service frontend --url
```

Destroy (when done):

```bash
cd infra/terraform
terraform destroy -auto-approve
```

Or:

```bash
./infra/delete.sh
```

Notes:

- Default context is `minikube` (override with `kube_context` in `terraform.tfvars`).
- Images default to `finsight-backend:local` and `finsight-frontend:local`.
- Keep using `k8s/finsight-minikube.yaml` if you want raw manifests; use Terraform when you need demonstrable IaC workflow.

### Tests

```bash
pip install pytest
PYTHONPATH=. pytest tests/
```

## Baseline inference (`inference.py`)

Uses the **OpenAI** Python client against any OpenAI-compatible endpoint.

```bash
export FINANCIAL_ENV_BASE_URL="http://localhost:7860"
export API_BASE_URL="https://api-inference.huggingface.co/v1"   # or https://api.openai.com/v1
export MODEL_NAME="meta-llama/Llama-3.1-8B-Instruct"
export OPENAI_API_KEY="..."   # or HF_TOKEN for Inference API
python inference.py
```

Stdout lines **`[START]`**, **`[STEP]`**, **`[END]`** follow the hackathon format; results are written to `results.json`.

**Reproducibility:** episodes are seeded server-side (`metadata.episode_seed`). Re-run with the same seed via stateless `/step` (`task_name` + `episode_seed`) for exact replay.

## Client example

```python
from client import FinancialDocEnv
from models import FinancialAction

env = FinancialDocEnv("http://localhost:7860")
obs = env.reset(task_name="anomaly_classification")
state = env.episode_state()  # POST /state

action = FinancialAction(
    action_type="classify",
    value="TX-101-03,TX-101-08",
    confidence=0.72,
    reasoning="Duplicate vendor pattern and threshold-hugging rows flagged.",
)

nxt = env.step(action)
print(nxt["reward"], nxt["done"], nxt.get("info", {}))
```

## `openenv.yaml`

Manifest includes `spec_version`, `type: space`, `runtime: fastapi`, `app`, `port`, and enumerated tasks for `openenv validate`.
