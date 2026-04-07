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
# Financial Document OpenEnv Environment

Financial document analysis is a high-impact, real-world workflow where analysts and auditors repeatedly triage noisy statements, extract decision-critical KPIs, and flag compliance risks under uncertainty. This environment turns that workflow into a reproducible RL-style benchmark with structured observations, typed actions, deterministic graders, and partial-credit rewards that encourage both correctness and calibrated confidence.

## Observation Space

| field | type | description |
|---|---|---|
| document_id | str | Unique synthetic document identifier |
| document_type | str | One of income_statement, balance_sheet, transaction_log |
| content | str | Full synthetic financial document text |
| task_description | str | Instruction for the current task |
| task_difficulty | str | easy, medium, or hard |
| legal_actions | List[str] | Allowed action_type values for current task |
| step_in_episode | int | Current step index in episode |
| max_steps | int | Maximum episode steps |
| running_score | float | Partial score within episode |
| done | bool | Whether episode is complete |
| reward | Optional[float] | Reward from latest step |
| metadata | Dict[str, Any] | Additional task and grading metadata |

## Action Space

| field | type | description |
|---|---|---|
| action_type | str | classify, extract_kpi, flag_issue, recommend |
| value | str | Action payload (IDs, JSON, recommendation text) |
| confidence | float | Confidence in [0.0, 1.0] |
| reasoning | str | Short rationale |

## Tasks

| name | difficulty | description | grader method |
|---|---|---|---|
| anomaly_classification | easy | Identify anomalous transaction IDs from log | F1 score over predicted vs ground-truth anomaly IDs |
| kpi_extraction | medium | Extract revenue, gross_profit, net_income, ebitda | Mean of relative-accuracy scores per KPI with invalid JSON penalty |
| compliance_assessment | hard | Flag compliance issue types with severities | Weighted precision/recall-style score on issue types + hallucination penalty |

## Setup

### Local dev

```bash
cd financial_env
pip install -r requirements.txt
uvicorn server.app:app --reload --host 0.0.0.0 --port 7860
```

### Docker

```bash
docker build -t financial-env .
docker run -d -p 7860:7860 financial-env
```

### Run baseline

```bash
export API_BASE_URL="https://api-inference.huggingface.co/v1"
export MODEL_NAME="meta-llama/Llama-3.1-8B-Instruct"
export HF_TOKEN="your_token_here"
export FINANCIAL_ENV_BASE_URL="http://localhost:7860"
python inference.py
```

### HF Spaces deploy

Push the entire repository to a Hugging Face Space configured with SDK: docker.

## Example Loop

```python
from client import FinancialDocEnv
from models import FinancialAction

env = FinancialDocEnv("http://localhost:7860")
obs = env.reset(task_name="anomaly_classification")

action = FinancialAction(
    action_type="classify",
    value="TX-101-03,TX-101-08",
    confidence=0.72,
    reasoning="Two records show duplicate and 10x amount spike patterns.",
)

next_obs = env.step(action)
print(next_obs["reward"], next_obs["done"])
```
