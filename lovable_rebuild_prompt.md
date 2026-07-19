# VC Brain — Lovable UI Rebuild Prompt (disaster recovery)

Purpose: if the Lovable project is lost (account change, credits, deleted project),
any agent connected to the Lovable MCP (`https://mcp.lovable.dev`) can rebuild the
entire UI from this file in ONE build prompt. This spec is the consolidated end
state of all iterations as of 2026-07-19 — do NOT replay the iteration history.

Current live project (skip rebuild if still accessible):
- project_id: `3a160169-7f8d-486c-a77b-7c2f68232253`, workspace `pyoiyyfJltqA8a0gykmF`
  (account elenantapyan28@gmail.com)
- Live: https://vc-brain.lovable.app · Editor: https://lovable.dev/projects/3a160169-7f8d-486c-a77b-7c2f68232253
- The live project is far ahead of this base prompt: persona apps (investor +
  founder), memo view, outreach loop, thesis tab, profile/settings — see
  `lovable_prompt_v2.md` (repo root) — plus a runtime data connection (below).
  A code snapshot also lives in `frontend/` on main (may lag the live app).

FULL REBUILD SEQUENCE (in order, one send_message each):
1. The base build prompt below (landing + auth + onboarding).
2. The entire `lovable_prompt_v2.md` build prompt (persona apps, memo,
   outreach, thesis, settings).
3. The data connection message (section at the bottom of this file).
4. `set_project_knowledge` with the project invariants (data connection, api.ts
   boundary, 3-axis never averaged, per-claim trust, criteria placeholders).

## Agent workflow

1. `create_project` with the build prompt below as `initial_message` (pass
   `workspace_id` if more than one workspace exists).
2. Wait for completion (`get_message` if it times out). Review the response;
   fix issues with follow-up `send_message` calls to the same project_id.
3. `deploy_project` with `name: "vc-brain"` → target URL https://vc-brain.lovable.app.
   The slug is per-account; if taken, use e.g. `vc-brain-2` and report the URL.
4. Verify: curl the live URL for HTTP 200 and run the checklist at the bottom.

Note: Lovable's default stack is TanStack Start (React + TanStack Router,
file-based routes) + Tailwind + shadcn/ui, built with Bun. Don't fight it.

## Build prompt (send verbatim as initial_message)

---

Build the VC Brain interface. VC Brain is an AI platform for investors and
accelerators: it takes an investment thesis, sources founders from public
signals, scores and ranks them, and generates outreach and investment memos
with per-claim trust scores.

1. LANDING PAGE (/):
- Futuristic tech aesthetic aimed at investors and accelerators: dark theme,
  sleek gradient/glow accents, modern typography. Polished and credible, not
  gimmicky.
- Hero section with the product name "VC Brain", a strong call-to-action slogan
  (e.g. "Find tomorrow's founders before the market does" — improve on it if
  you can), a short subline explaining the product, and two prominent CTAs:
  "Sign up" (primary) and "Log in" (secondary).
- Below the hero: a section visualizing the pipeline (Thesis → Source → Score →
  Rank → Outreach → Memo) and 3–4 value-prop cards (e.g. cold-start friendly
  signals, per-claim trust scores, full traceability, power-law aware scoring).
  No fake testimonials, no fake metrics.

2. AUTH FLOWS:
- Both Log in and Sign up start with a persona choice rendered as two
  selectable cards: "I'm an Investor" / "I'm a Founder".
- Log in: after persona choice → email + password form.
- Sign up: after persona choice → email + password, then a persona-specific
  onboarding step:
  - INVESTOR onboarding: "What are you interested in?" — multi-select chips for
    sectors (AI/ML, Fintech, Climate, Healthtech, Dev Tools, Consumer, Deep
    Tech, Biotech, Cybersecurity, SaaS) and stages (Pre-seed, Seed, Series A),
    plus an "Other" chip that reveals a free-text input.
  - FOUNDER onboarding: the same interests multi-select (for their company's
    space) PLUS additional optional fields: company name, one-line description,
    website URL, location, pitch deck upload (PDF — just capture the file
    client-side, no storage backend yet), and a free-text "anything else we
    should know".
- Every step must be reversible: visible "Back" controls from credentials back
  to persona choice and from onboarding back to credentials (login too), with
  NO data loss going back and forward — persona, typed email/password, selected
  chips, and founder fields all persist. Show a step indicator ("Step X of 3")
  in the sign-up flow.
- Registration completes ONLY at the end: keep all sign-up data in in-memory
  flow state until the user submits the FINAL onboarding step — only then
  create the account, establish the session, and redirect to the dashboard.
  Abandoning mid-flow (navigating away, closing the tab) must leave no account
  and nothing persisted.
- After completing sign-up (or logging in), route to a minimal authenticated
  dashboard placeholder that greets the user by email, shows their persona and
  captured onboarding data, and has a Log out action. This dashboard is a
  stub — the real one comes later.

3. ACCOUNT MODEL:
- The same email may hold TWO separate accounts — one as investor and one as
  founder — created independently. Key stored users by email + persona, not
  email alone. The duplicate-account error on sign-up triggers only if an
  account with the same email AND persona exists. Login resolves the account
  by the persona chosen first; a missing combination shows a clear error like
  "No investor account for this email". The session records both email and
  persona so the dashboard shows the right account.

4. TECHNICAL CONSTRAINTS:
- No Supabase or any auth backend. Mock authentication entirely client-side
  (localStorage). It will later be replaced by a Python FastAPI backend, so put
  ALL auth/onboarding operations behind a single API client module
  (src/lib/api.ts) with clearly named stub functions — completeSignUp (atomic:
  account creation + onboarding save + session), logIn, getCurrentUser,
  logOut — so swapping in real HTTP calls later touches only that file.
- Forms validate (email format, password min 8 chars) and everything is
  responsive.

---

## Post-build verification checklist

- Landing renders dark/futuristic with hero, slogan, pipeline viz, value cards.
- Sign up as investor: persona → credentials → interest chips (+ Other free
  text) → dashboard shows email, persona, interests.
- Sign up as founder with the SAME email succeeds (separate account); founder
  onboarding shows the optional company fields + PDF capture.
- Back buttons work on every step both flows; entered data survives
  back-and-forward.
- Abandon sign-up at the onboarding step, reload: no session, no account —
  logging in with those credentials fails.
- Log in with wrong persona for an email shows the "no X account" error.
- All auth calls go through src/lib/api.ts only (grep the routes for
  localStorage — there should be none outside api.ts).
- Deployed URL returns HTTP 200 and serves the app (body is client-rendered;
  check the <title> in raw HTML, view text in a browser).

## Data connection message (step 3 — send after the v2 build)

Send verbatim (adjust branch if the dataset moved to main):

---

Mechanical integration task — no redesign. In src/lib/api.ts add a runtime
data source: const SOURCED_URL =
"https://raw.githubusercontent.com/tigranmargaryan13/vc-brain/ui/data/ui/sourced_founders.json";
plus a loader with a module-level cache (fetch, validate it's an array of
founder objects with id/name/projects/scores/evidence, cache, return [] on any
failure so mocks still work offline) and
`async function allFounders() { return [...MOCK_FOUNDERS, ...(await loadSourced())]; }`.
Use `await allFounders()` instead of MOCK_FOUNDERS in searchFounders,
getFounder, generateMemo, and the best-match seeds in listNotifications.
The JSON is already exactly FounderProfile[] shape. In the Hunt page filter
consts add "Unknown" to SECTORS and STAGES, and "New York", "Toronto",
"Los Angeles", "Vancouver", "Remote", "Unknown" to LOCATIONS.

---

The dataset itself is produced by `scripts/build_ui_dataset.py` (roster:
founder_product_info.csv + real pipeline scores via `python -m
sourcing.export`; seeded-random fills for missing fields). Regenerate + push
to refresh the app — no Lovable credits needed for data-only updates.
