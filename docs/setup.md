# Setup Guide

## Prerequisites

- Python 3.9+
- Node.js 18+
- Git
- Homebrew (for Ollama)

## Steps

### 1. Clone Repository

```bash
git clone <repo-url>
cd insurance-agent
```

### 2. Python Virtual Environment

```bash
python3 -m venv .venv
```

### 3. Install Dependencies

```bash
.venv/bin/pip install --upgrade pip
.venv/bin/pip install --upgrade pip
.venv/bin/pip install google-genai pypdf pdfplumber pydantic python-dotenv httpx playwright openpyxl tqdm
```

### 4. Install Playwright Browsers

```bash
.venv/bin/playwright install chromium
```

### 5. Install Ollama

```bash
brew install ollama
```

### 6. Environment Variables

```bash
cp .env.example .env
# Fill in your API keys: GEMINI_API_KEY, GROQ_API_KEY, VOYAGE_API_KEY
```

### 7. Verify API Keys

```bash
.venv/bin/python backend/scripts/test_gemini.py
.venv/bin/python backend/scripts/test_groq.py
.venv/bin/python backend/scripts/test_voyage.py
```

## Running the Project

*To be filled in after Phase 3 deployment.*

## API Reference

| Key | Source | URL |
|-----|--------|-----|
| Gemini 2.5 Flash | Google AI Studio | https://aistudio.google.com |
| Groq Llama 3.3 70B | Groq Console | https://console.groq.com |
| Voyage-4-lite | Voyage AI | https://www.voyageai.com |
