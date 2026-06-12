import os

import requests
from dotenv import load_dotenv


load_dotenv()

base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
model_name = os.getenv("OLLAMA_MODEL", "llama3")
timeout_seconds = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))

response = requests.post(
    f"{base_url}/api/generate",
    json={
        "model": model_name,
        "prompt": "Say hello in one short sentence.",
        "stream": False,
        "options": {
            "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.2")),
            "top_p": float(os.getenv("OLLAMA_TOP_P", "0.95")),
            "num_predict": int(os.getenv("OLLAMA_NUM_PREDICT", "2048")),
        },
    },
    timeout=timeout_seconds,
)
response.raise_for_status()

print(response.json().get("response", "").strip())
