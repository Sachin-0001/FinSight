# debug_easy.py
import os
from dotenv import load_dotenv
from openai import OpenAI
from client import FinancialDocEnv
from models import FinancialAction

load_dotenv()

api_key = os.environ.get("HF_TOKEN") or os.environ.get("OPENAI_API_KEY", "")
api_base = os.environ.get("API_BASE_URL", "https://api-inference.huggingface.co/v1")
model_name = os.environ.get("MODEL_NAME", "meta-llama/Llama-3.1-8B-Instruct")

if not api_key:
    raise SystemExit("ERROR: set HF_TOKEN env var before running")

llm_client = OpenAI(base_url=api_base, api_key=api_key)
env = FinancialDocEnv(base_url="http://localhost:8000")

# Reset and print the full document
observation = env.reset(task_name="anomaly_classification")
# Add right after env.reset()
import requests
# peek at what the server has stored
print("\n=== CHECKING SEED CONSISTENCY ===")
print("Reset seed:", observation["metadata"].get("episode_seed"))
print("=== DOCUMENT ===")
print(observation["content"])
print("\n=== EPISODE SEED ===")
seed = observation["metadata"].get("episode_seed")
print(seed)

# Build prompt and print it
from inference import _build_prompt
prompt = _build_prompt(observation)
print("\n=== PROMPT SENT TO LLM ===")
print(prompt)

# Call LLM
response = llm_client.chat.completions.create(
    model=model_name,
    messages=[
        {"role": "system", "content": "You output strict JSON only."},
        {"role": "user", "content": prompt},
    ],
    temperature=0.2,
)
raw = response.choices[0].message.content
print("\n=== RAW LLM RESPONSE ===")
print(repr(raw))

# Parse
from inference import _json_extract
import json
parsed = _json_extract(raw)
print("\n=== PARSED JSON ===")
print(parsed)

if parsed:
    try:
        action = FinancialAction.model_validate(parsed)
        print("\n=== ACTION VALUE ===")
        print(repr(action.value))
        print("=== ACTION TYPE ===")
        print(action.action_type)

        result = env.step(action)
        print("\n=== REWARD ===")
        print(result.get("reward"))
        print("\n=== GROUND TRUTH ===")
        gt = result.get("metadata", {}).get("ground_truth", {})
        print("anomaly_ids:", gt.get("anomaly_ids"))
        print("seed in gt:", gt.get("seed"))
        print("episode_seed from reset:", seed)
        print("seeds match:", gt.get("seed") == seed)
    except Exception as e:
        print(f"\nERROR building/stepping action: {e}")
else:
    print("\nPARSE FAILED — raw response could not be parsed as JSON")
    print("This means _heuristic_action is being used instead")