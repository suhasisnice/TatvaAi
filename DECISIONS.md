# Decisions

One line each: decision, then why. Newest last.

1. **Rebuilt from scratch on 2026-10-26; old code archived in `../_old/pramaanai`.** Clean start for two people; copy from the archive only on purpose.
2. **Scope follows `PramaanAI_SIH26261_Team_Guide.pdf`**, tiered P0/P1/P2 in `BUILD_GUIDE.md`. Cut P2 first.
3. **SQLite first, same models on PostgreSQL later; no PostGIS.** Lat/lon columns are enough; one less service.
4. **Tables via `create_all` for now; add Alembic before the first Postgres deploy.** Schema is still moving; migrations now would churn.
5. **No Celery/Redis/MinIO at the start.** The pipeline runs synchronously (2 to 5 s). Add Celery only for the nightly alert job.
6. **Contracts frozen early** (rule schema, models, OpenAPI, Flag/Fact) so the frontend builds against a stub API in parallel.
7. **Stub API returns fixed data for institutions A, B, C** (GREEN 0, AMBER 30, RED 245.05 from the guide) so screens can be built before engines exist.
8. **Mock issuers are a separate FastAPI app (port 9000)** and adapters read their base URL from env, so real APIs can replace them.
9. **FreeLLMAPI (`tools/freellmapi`) and OmniRoute are dev helpers only**, bound to 127.0.0.1. Not part of the product, no keys in the repo.
