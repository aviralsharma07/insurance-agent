# Phases — Living Implementation Plan

## Phase 0 — Foundation: Docs, Data Pruning & Schema Design
**Status: complete**

- [x] Docs initialized (architecture, data-sources, decisions, phases, setup)
- [x] Project setup (venv, deps, Playwright, Ollama, 3 API keys)
- [x] IRDAI UIN lifecycle scraper (1,082 products, 1,099 versions, 32 insurers)
- [x] IRDAI historical performance scraper
- [x] PDF audit & classification (1,067 PDFs → 781 policy wordings, 119 circulars, 65 pruned)
- [x] Supabase schema design & migration (12 tables + pgvector + RLS)
- [x] Schema seeded (32 insurers, 1,082 products, 1,084 versions)

## Phase 1 — Feature Extraction Pipeline
**Status: not started**

Feature schema definition (60+ Pydantic fields), multi-pass extraction engine (Gemini vision), extraction validation and full batch run on all ~781 active policies.

## Phase 2 — RAG Pipeline
**Status: not started**

Generate embedding text from features, embedding pipeline (Voyage-2 → pgvector), RAG query service, RAG QA test suite (9 queries must pass).

## Phase 3 — Agent & API Backend
**Status: not started**

FastAPI application structure, agent orchestrator with custom tool calling, fallback chain (Groq → Gemini → Ollama), deployment to GCP Cloud Run.

## Phase 4 — Frontend
**Status: not started**

Next.js setup (TypeScript, Tailwind, App Router), chat page with streaming, product browse and detail pages, comparison page, SEO/AEO foundation, Vercel deployment.

## Phase 5 — First Users & Validation
**Status: not started**

Reddit distribution, user feedback collection. Begins only after 50 real users and 5 positive signals.

## Phase 6 — Post-MVP: Compliance Engine, Monetisation, Data Visualisation
**Status: not started**

Everything here is post-MVP. Compliance engine, monetisation (Razorpay + Supabase Auth), data visualisation.

---

## Budget Overview

| Phase | One-Time Cost | Ongoing Cost |
|-------|---------------|--------------|
| Phase 0 | $0 | $0 |
| Phase 1 | ~$2.55 (Gemini API) | $0 |
| Phase 2 | $0 (Voyage-2 free tier) | $0 |
| Phase 3 | $0 | ~$0.04 per 1K queries |
| Phase 4 | $0 | $0 |
| **Total** | **~$2.55** | **~$0.04 per 1K queries** |
