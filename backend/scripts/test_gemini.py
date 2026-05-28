"""Verify Gemini 2.5 Flash API key works."""

import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("FAIL: GEMINI_API_KEY not set in .env")
    exit(1)

from google import genai

client = genai.Client(api_key=api_key)
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Say 'Gemini API is working' and nothing else.",
)
print("Gemini response:", response.text)
assert "working" in response.text.lower()
print("PASS: Gemini API key verified.")
