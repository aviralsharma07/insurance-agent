# Architecture

## Current Structure (Phase 0)

```
insurance-agent/
├── docs/
│   ├── architecture.md       — this file
│   ├── data-sources.md       — all scraped sources, URLs, status
│   ├── decisions.md          — technical and product decisions log
│   ├── phases.md             — living version of the implementation plan
│   └── setup.md              — exact steps to run the project from scratch
├── .gitignore
└── IMPLEMENTATION_PLAN.md
```

## What the System Will Become

An AI-powered health insurance intelligence agent for India. It will combine structured feature extraction (multi-pass Gemini 2.5 Flash parsing of policy wordings into 60+ Pydantic fields), RAG over policy wordings and IRDAI circulars (pgvector in Supabase, Voyage-4-lite embeddings), and an agent orchestrator (custom, Google GenAI SDK function calling) to answer user queries, compare policies across insurers, and provide honest, data-backed recommendations — all with zero commission conflicts.

## System Architecture (Target)

```
User → Next.js (Vercel) → FastAPI (Cloud Run) → Agent Orchestrator
                                                     ├── Groq Llama 3.3 70B (primary)
                                                     ├── Gemini 2.5 Flash (fallback)
                                                     └── Ollama Gemma 3 27B (local fallback)
                                              Agent Tools →
                                               ├── search_policies (Voyage-4-lite → pgvector)
                                               ├── search_circulars (Voyage-4-lite → pgvector)
                                                     ├── compare_policies (structured features)
                                                     ├── filter_policies (feature query)
                                                     └── get_insurer_history (IRDAI data)

Data Sources → Multi-Pass Extraction → Supabase (PostgreSQL + pgvector)
                (Gemini vision)                ├── products / product_versions
                                               ├── policy_features (jsonb)
                                               ├── policy_chunks (vector 1024d)
                                               ├── circular_chunks (vector 1024d)
                                               ├── irdai_historical
                                               └── conversations
```
