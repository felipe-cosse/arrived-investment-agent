# Lessons

## 2026-07-09 — "Use real data" means *exclusively* real

When the user asked for real Arrived data, I delivered real data coexisting with the demo seeds (seeds retired to `closed` but still in the DB and visible in the explorer). The user then had to correct: "Don't use fake data."

**Rule:** when a user asks to replace mock/demo data with real data, default to *removing* the mock data from every runtime path (display, storage, prompts, docs), not layering real data on top. Offer "keep demo as fallback" as the explicit opt-in, not the default. Test fixtures are the only sanctioned home for synthetic data — and say so out loud when the spec (like R21 here) baked the mock data into a MUST rule.
