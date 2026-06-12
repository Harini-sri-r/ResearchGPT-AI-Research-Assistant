import os

from dotenv import load_dotenv
import google.generativeai as genai


load_dotenv()

api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
timeout_seconds = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "120"))

if not api_key:
    raise RuntimeError("GEMINI_API_KEY is missing. Add it to .env first.")

genai.configure(
    api_key=api_key,
    transport="rest",
)

model = genai.GenerativeModel(model_name)
response = model.generate_content(
    "Say hello in one short sentence.",
    request_options={
        "timeout": timeout_seconds,
    },
)

print(response.text)
