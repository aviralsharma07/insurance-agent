# Technical & Product Decisions

## 2026-05-28 — Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent framework | Custom (Google GenAI SDK) | No LangChain bloat, direct tool control, lightweight |
| Embedding model | Voyage-2 (1536d) | Free tier (100M tokens/mo), high quality, no infra |
| Vector DB | Supabase pgvector | Persistent across deployments, same platform as data, no separate service |
| Extraction model | Gemini 2.5 Flash | Native PDF vision, handles tables and layouts, generous free tier |
| Agent model (primary free) | Groq Llama 3.3 70B | Free API, fast inference, excellent reasoning, no local resource use |
| Agent model (local secondary) | Gemma 3 27B Q4 via Ollama | Fits M4 24GB cleanly, zero API cost, unlimited use, Metal accelerated |
| Agent model (extraction fallback) | Gemini 2.5 Flash | Same model as extraction, already authenticated |
| PDF text extraction | Gemini vision (not pypdf) | Avoids table and layout destruction common in Indian insurance PDFs |
| Backend deployment | GCP Cloud Run asia-south1 | Free tier 2M req/month, no cold start data loss, Mumbai region |
| Frontend deployment | Vercel | Best Next.js hosting, free tier, auto-deploy from GitHub |
| Repository structure | Monorepo | Single developer, unified docs, Vercel and Cloud Run both support subdirectory deploys |
| Auth for v1.0 MVP | None | No signup friction at zero users, session state in memory is sufficient |

## Working Rules

- **One task at a time.** Complete one task fully and verify it works before starting the next.
- **Do not install what you do not need yet.** Install dependencies only for the phase you are currently in.
- **Verify before moving on.** Every phase has an explicit Done State. Do not move to next until every item is confirmed working.
- **The docs folder is updated in the same commit as the code it describes.** Same commit, not later.
- **Test run feature extraction before full batch.** Pick 8 different policy wordings, test, validate, then improve.
