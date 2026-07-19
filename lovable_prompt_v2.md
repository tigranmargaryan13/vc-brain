# VC Brain — Lovable prompt v2 (persona apps + memo/outreach/thesis) — DRAFT, not sent

Send verbatim via send_message to project 3a160169-7f8d-486c-a77b-7c2f68232253
after user confirmation and once workspace credits are available.
Grounded in: challenge brief (Appendix 1 memo checklist, Thesis Engine spec,
3-axis screening). Criteria are deliberately generic placeholders — the team
has NOT finalized the criteria list; do not bake in any specific criteria.

---

This is a prototype — there is no real dataset yet. Use believable mock data
(behind the API layer, see TECHNICAL at the end) or well-designed empty states.
Keep the existing landing page, visual style (dark futuristic), and auth flows;
everything below extends them. Design north star: "Notion-level
approachability, Bloomberg-level analytical depth" — for a non-technical
investor.

## PART A — Registration fixes

1. Same email, two personas: the same email may hold TWO separate accounts —
   one as investor and one as founder — created independently, since the same
   person can be both. Key stored users by email + persona (not email alone).
   The duplicate-account error on sign-up triggers only when an account with
   the same email AND same persona exists. Login (which already asks persona
   first) resolves the account by email + persona; a missing combination shows
   a clear error, e.g. "No investor account for this email — did you mean to
   log in as a founder?". The session records both email and persona.

2. Founder sign-up — company step skippable: on the founder onboarding step,
   add a secondary action "Add later" that completes registration without any
   company data. Founders can add companies afterwards from the app (Part B).
   If they DO fill the company form during sign-up, it follows the same rules
   as the shared company form below (deck, name, industry mandatory).

## PART B — Scoring model shown across the app (core product identity)

Wherever a founder/project is scored, show THREE independent axes — NEVER
combined or averaged into one number:
- Founder: 0–100 meter. Built from public signals; a missing signal means
  "unknown", never a penalty.
- Market: a rating chip — Bullish / Neutral / Bear.
- Idea vs. Market: a chip — "Survives as-is" / "Pivot potential" / "At risk".
Each axis also shows a trend arrow (improving / stable / declining).
Additional badges:
- Cold-start badge: when a profile has little public signal, show
  "Cold start — unknowns are NOT negatives" instead of low scores.
- Trust: every factual claim (in detail views and memos — NOT on list cards,
  which stay scannable) carries a small per-claim Trust chip — High / Medium /
  Low — with a source link (mock URL) and a state: corroborated /
  uncorroborated / contradicted (contradicted renders as a warning flag).

## PART C — Persona apps

APP SHELL (both personas): left sidebar in the dark futuristic style —
product logo at top, 3 nav items, and the user/avatar menu pinned at the
bottom (email + persona badge; opens Profile & Settings). A slim top header
on every page shows the page title on the left and a notification BELL icon
with an unread-count badge on the right — notifications are NOT a sidebar
tab. The sidebar collapses to icons on mobile. Investor accounts see the
Investor app, founder accounts the Founder app; routes are guarded by
persona, and logged-out users are redirected to login.

NOTIFICATION BELL (header, both personas): clicking opens a popover feed,
newest first, unread highlighted, "mark all as read" action.
- Investor feed: "best match" alerts that reference the thesis ("Matches your
  thesis: AI/ML · Pre-seed · Berlin"); clicking an alert deep-links to that
  founder's detail view.
- Founder feed: invitations from investors — each shows the investor's
  outreach message with Accept / Decline actions inline (mock state changes
  only). Accepting updates the status the investor sees.

### INVESTOR app — 3 sidebar items

1. Dashboard — portfolio tracking: current investments and projects invested
   in (company, sector, stage, amount, date, status), plus summary stats at
   the top (total invested, active deals, sectors covered). Mock data. For a
   brand-new account, the empty state is a guided next-step card: "Set your
   thesis → Hunt founders".

2. Hunt Founders — search and filter founder profiles: keyword search plus
   filters for sector, stage, and location, and a segmented control
   "All | Saved (n)" — Saved is NOT a separate tab; it's a view toggle here
   that shows only saved founders/projects. One founder can have multiple
   companies/projects, so results are founder cards listing their project(s).
   Each card shows the three score axes (Part B), cold-start/contradiction
   badges (keep per-claim trust chips OFF cards — they live in the detail
   view and memo, cards stay scannable), a Save/Unsave action, an "Invite to
   apply" action, and an invitation status chip once invited (Invited /
   Accepted / Declined) with re-invite disabled. Clicking a card opens the
   founder/project detail view; returning restores the previous filters,
   view toggle, and scroll position. Empty states for both no-results and
   no-saved-yet.

3. Thesis — the investor's fund thesis, editable: sectors (multi-select),
   stage, geography, check size, ownership target, risk appetite — plus
   criteria weights: sliders over criteria groups served by getCriteria()
   (see TECHNICAL — do NOT hardcode criteria in components; use generic
   placeholder groups like Team, Traction, Market, Product for now, the
   real criteria list is not final). Saving shows a note that matches and
   notifications are ranked through this lens. Prefill from the interests
   chosen at onboarding.

FOUNDER / PROJECT DETAIL VIEW (opened from Hunt or Saved):
- Header: founder + project(s), location, stage, sector, the three axes with
  trends, badges.
- Evidence list: the public signals behind the Founder axis (e.g. "shipped 3
  repos in 6 months", "hackathon winner", "paper published"), each with its
  Trust chip + source link. Unknown signals listed as "unknown — not counted
  against".
- "Generate memo" button → brief loading state → INVESTMENT MEMO rendered
  in-page. Investors read the conclusion first, so the VERDICT is a pinned
  card at the TOP: recommendation chip (e.g. "Conditional yes"), the three
  axes restated, and the top reasons. Below it, collapsible sections
  (expanded by default, so the memo stays skimmable):
  1. Company snapshot — one paragraph.
  2. Investment hypotheses — "why invest" bullets.
  3. SWOT — four short evidence-backed lists.
  4. Problem & product.
  5. Traction & KPIs.
  6. Gaps & due-diligence log — explicit list of what is missing/unverified,
     stated plainly, e.g. "Cap table: not disclosed", "Revenue: unverified —
     founder claim only". NEVER invent missing data.
  Every factual claim line in sections 1–5 carries its per-claim Trust chip +
  source + corroborated/uncorroborated/contradicted state.
- "Invite to apply" CTA: opens a modal previewing a short generated outreach
  message (editable textarea, mock template referencing why they match the
  thesis) with a Send action.

### FOUNDER app — 3 sidebar items

1. Dashboard — ongoing statistics: how many times shortlisted/saved by
   investors, cases per project/company, invitation → acceptance funnel,
   profile views. Simple stat cards; a small chart or two is welcome. Mock
   data, with proper empty states for a brand-new account.

2. My Companies — companies listed as cards, plus an "Add start-up" CTA that
   opens the shared company form: MANDATORY pitch deck upload (PDF, captured
   client-side only), company name, and industry (select with an "Other"
   option revealing free text); OPTIONAL website, location, one-line
   description, and notes. Clicking a company card opens its detail page
   where all fields can be edited. The company form is ONE reusable component
   used in founder sign-up, Add start-up, and edit mode.

3. Fundraising Criteria — read-only insights page: the criteria investors on
   the platform prioritize, rendered from the SAME getCriteria() source as
   the investor Thesis tab — ranked list with relative weight bars and a
   one-line explanation each (generic placeholder criteria for now). Include
   a small footnote: "Criteria are provisional and will evolve."

(Founder invitations live in the header notification bell — see APP SHELL —
not in the sidebar.)

### PROFILE & SETTINGS — both personas

Accessible from the avatar/user menu at the bottom of the sidebar (shows email
+ persona badge). One page with sections:
- Profile: display name (editable), email (read-only), persona badge, and
  persona-specific fields — investor: edit their interest chips (same
  component as onboarding); founder: edit personal details (location,
  bio/links). Changes save through the API layer.
- Security: change password (mock — validates current password, min 8 chars).
- Notification preferences: toggles (e.g. best-match alerts / invitations,
  email digest) — mock state only.
- Account: log out, and a "Delete account" action with a confirm dialog
  (mock — removes the account for this persona only; the other persona's
  account under the same email survives).

DEMO LOOP REQUIREMENT: invitations must work across accounts in the same
browser — an investor sends an invite, then logging in as a founder account
shows it in Notifications, and accepting updates what the investor sees. Store
this shared state via the API layer (localStorage).

## TECHNICAL

- Keep ALL data operations behind src/lib/api.ts: extend it with typed stub
  functions (e.g. listInvestments, searchFounders, getFounder, generateMemo,
  saveProject, unsaveProject, listSaved, getThesis, saveThesis, getCriteria,
  sendInvitation, listNotifications, markNotificationRead,
  respondToInvitation, listCompanies, addCompany, updateCompany,
  updateProfile, changePassword, updateNotificationPrefs, deleteAccount) that
  serve
  mock data (in-module constants; localStorage for user-created state). A
  Python FastAPI backend will replace this file later — nothing outside it
  may touch localStorage or mock data.
- getCriteria() is the single source of truth for criteria groups + weights
  (used by Thesis sliders AND Fundraising Criteria page) — the team will
  finalize criteria later, so components must render whatever it returns.
- Mock dataset: 8–12 founder profiles with 1–3 projects each (varied sectors,
  stages, locations, axes, trust levels). Realistic but clearly fictional
  names. Include these three demo personas:
  - A cold-start founder: almost no public signal, cold-start badge, memo
    full of explicit "unknown / not disclosed" gap lines, but high ambition
    signals — the "unknowns are not negatives" showcase.
  - A strong full-signal founder: complete memo, mostly corroborated claims,
    verdict "Conditional yes".
  - A founder with a seeded contradiction: one claim marked contradicted
    (e.g. claimed revenue contradicts a public source), flagged visibly in
    card, detail, and memo.
- Pre-generate the memo content for these three; other profiles may share a
  simpler memo template.
- Every action gives feedback via a toast (saved, invite sent, invitation
  accepted, thesis saved, settings updated).
- Everything responsive; forms validate; keep the existing step indicator and
  back-navigation behavior in auth flows.
