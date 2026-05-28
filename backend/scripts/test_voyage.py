"""Verify Voyage-2 API key works."""

import os
from dotenv import load_dotenv
import httpx

load_dotenv()
api_key = os.getenv("VOYAGE_API_KEY")
if not api_key:
    print("FAIL: VOYAGE_API_KEY not set in .env")
    exit(1)

resp = httpx.post(
    "https://api.voyageai.com/v1/embeddings",
    headers={"Authorization": f"Bearer {api_key}"},
    json={"model": "voyage-4-lite", "input": ["Hello world"]},
    timeout=30,
)
resp.raise_for_status()
data = resp.json()
assert len(data["data"]) == 1
assert len(data["data"][0]["embedding"]) == 1024
print(f"Voyage-4-lite response: embedding dim={len(data['data'][0]['embedding'])}")
print("PASS: Voyage-4-lite API key verified.")
