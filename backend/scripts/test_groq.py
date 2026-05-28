"""Verify Groq API key works with Llama 3.3 70B."""

import os
from dotenv import load_dotenv
import httpx

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    print("FAIL: GROQ_API_KEY not set in .env")
    exit(1)

resp = httpx.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json={
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "user", "content": "Say 'Groq API is working' and nothing else."}
        ],
    },
    timeout=30,
)
resp.raise_for_status()
text = resp.json()["choices"][0]["message"]["content"]
print("Groq response:", text)
assert "working" in text.lower()
print("PASS: Groq API key verified.")
