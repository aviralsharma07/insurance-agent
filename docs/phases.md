# Phases — Living Implementation Plan

## Phase 0 — Foundation: Docs, Data Pruning & Schema Design
**Status: not started**

Initialize docs/ folder, project setup, IRDAI UIN lifecycle scraper, IRDAI historical performance scraper, PDF audit & classification, Supabase schema design.

## Phase 1 — Feature Extraction Pipeline
**Status: not started**

Feature schema definition (60+ Pydantic fields), multi-pass extraction engine (Gemini vision), extraction validation and full batch run on all ~700 active policies.

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
