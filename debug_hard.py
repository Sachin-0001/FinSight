# debug_hard.py
import os, json
from dotenv import load_dotenv
from openai import OpenAI
from client import FinancialDocEnv
from models import FinancialAction
from inference import _build_prompt, _json_extract

load_dotenv()
llm_client = OpenAI(
    base_url=os.environ.get("API_BASE_URL"),
    api_key=os.environ.get("HF_TOKEN") or os.environ.get("OPENAI_API_KEY"),
)
model_name = os.environ.get("MODEL_NAME")
env = FinancialDocEnv(base_url=os.environ.get("FINANCIAL_ENV_BASE_URL", "http://localhost:7860"))

observation = env.reset(task_name="compliance_assessment")

response = llm_client.chat.completions.create(
    model=model_name,
    messages=[
        {"role": "system", "content": "You output strict JSON only."},
        {"role": "user", "content": _build_prompt(observation)},
    ],
    temperature=0.2,
)
raw = response.choices[0].message.content
print("=== RAW RESPONSE ===")
print(repr(raw))

parsed = _json_extract(raw)
print("\n=== PARSED ===")
print(parsed)

if parsed:
    try:
        action = FinancialAction.model_validate(parsed)
        print("\n=== ACTION VALUE (raw string) ===")
        print(action.value)
        
        # Parse the issues list
        issues_parsed = json.loads(action.value)
        print("\n=== ISSUES FOUND BY LLM ===")
        for issue in issues_parsed.get("issues", []):
            print(f"  type: {repr(issue.get('type'))}")
            print(f"  severity: {repr(issue.get('severity'))}")
            print()
        
        result = env.step(action)
        print("=== REWARD ===", result.get("reward"))
        print("\n=== GROUND TRUTH ISSUES ===")
        for issue in result.get("metadata", {}).get("ground_truth", {}).get("issues", []):
            print(f"  type: {repr(issue['type'])}, severity: {repr(issue['severity'])}")
        print("\n=== RED HERRINGS ===")
        print(result.get("metadata", {}).get("ground_truth", {}).get("red_herrings"))
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback; traceback.print_exc()
else:
    print("PARSE FAILED — raw was not valid JSON")
