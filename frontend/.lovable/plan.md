## Scope

Extend the existing VC Brain prototype (landing + auth already shipped) with the full logged-in product for both personas, plus registration fixes and a scoring model shown consistently across the app. All data still lives behind `src/lib/api.ts` (in-module mock constants + localStorage for user-created state).

## Assumptions

- "Send invitation" from investor → founder resolves by founder email + persona=founder. If no founder account exists yet, the invite is stored keyed by that email and surfaces the moment that founder registers/logs in (needed for the cross-account demo loop in one browser).
- "Ratings/trend" values on mock founders are static in-module constants; trends are hardcoded per profile (no time series).
- "Change password" validates current pw against the stored StoredUser record for that email+persona.
- Delete account removes only the `(email, persona)` row; the other persona survives.
- Founder Dashboard mock stats are derived from real invitation state where possible (invites sent to that founder), and static mock numbers for views/shortlists.
- The `Thesis` page prefills sectors/stage from onboarding interests on first visit; weights default to equal.

## Registration fixes (Part A)

- Change user key from `email` → `${email}::${persona}` in `api.ts`. Session stores `{ email, persona }` as JSON.
- `completeSignUp` error only when same email+persona pair exists; message hints the other persona if it exists.
- `logIn` resolves by email+persona; specific error "No {persona} account for this email — did you mean to log in as a {otherPersona}?" when the other persona exists.
- Founder onboarding step: add secondary "Add later" button that submits with empty company fields. If any company field filled, apply shared-form rules (deck + name + industry required). Reuse the shared CompanyForm component (see below).

## Scoring primitives (Part B)

New `src/components/scores/` with:
- `<FounderMeter value trend />` — 0–100 meter with trend arrow.
- `<MarketChip value trend />` — Bullish / Neutral / Bear.
- `<FitChip value trend />` — Survives as-is / Pivot potential / At risk.
- `<ColdStartBadge />`, `<ContradictionBadge />`.
- `<TrustChip level state sourceUrl />` — High/Med/Low + corroborated/uncorroborated/contradicted, with source link.
- `<ClaimLine text trust />` — used in detail evidence + memo sections 1–5.

Cards use axes + badges only (no TrustChips). Detail + memo use ClaimLines.

## API layer extensions (`src/lib/api.ts`)

Types: `Persona`, `User`, `Session`, `Trend`, `MarketRating`, `FitRating`, `TrustLevel`, `TrustState`, `Claim`, `EvidenceItem`, `Project`, `FounderProfile`, `Memo`, `Investment`, `Thesis`, `CriteriaGroup`, `Invitation`, `Notification`, `Company`, `NotificationPrefs`.

Functions (all async, mock, behind this file):
- Auth already there + `updateProfile`, `changePassword`, `updateNotificationPrefs`, `deleteAccount`, `getNotificationPrefs`.
- Investor: `listInvestments`, `searchFounders({q, sector, stage, location, savedOnly})`, `getFounder(id)`, `generateMemo(founderId, projectId)`, `saveProject(id)`, `unsaveProject(id)`, `listSaved()`, `getThesis()`, `saveThesis(t)`, `getCriteria()`, `sendInvitation({founderEmail, projectId, message})`, `listInvitationsForInvestor()`.
- Founder: `listCompanies()`, `addCompany(c)`, `updateCompany(id, c)`, `getCompany(id)`, `listFounderStats()`.
- Notifications: `listNotifications()`, `markNotificationRead(id)`, `markAllNotificationsRead()`, `respondToInvitation(id, 'accept'|'decline')`.

Mock data: 10 founder profiles with 1–3 projects, including the 3 demo profiles (cold-start, full-signal, contradiction). Pre-written memos for those 3; template memo for the rest that fills in name/sector but uses generic claims.

Cross-account invite storage: `vcbrain.invitations` (array). On investor "send", push `{id, investorEmail, founderEmail, projectId, message, status: 'sent', createdAt}`. On founder side, `listNotifications` reads invitations where `founderEmail == session.email && session.persona==='founder'` and synthesizes notification items. On investor side, notifications are best-match alerts (mock generator based on thesis) + status updates when a founder accepts/declines.

`getCriteria()` returns 4 groups: Team, Traction, Market, Product with default weights and one-line descriptions.

## Routing

New route files:
- `_app.tsx` — layout: guard (require session), sidebar + top header + notification bell. Persona-aware sidebar. `<Outlet />`.
- `_app.index.tsx` → redirect to `/dashboard` (persona-appropriate).
- Investor:
  - `_app.dashboard.tsx` — investor OR founder dashboard (branches on persona) — simpler: one route, two components.
  - `_app.hunt.tsx` — Hunt Founders list + filters + saved toggle.
  - `_app.founder.$id.tsx` — founder/project detail + memo.
  - `_app.thesis.tsx` — thesis + weights sliders.
- Founder:
  - `_app.companies.tsx` — My Companies list + Add.
  - `_app.companies.$id.tsx` — company detail/edit.
  - `_app.criteria.tsx` — Fundraising Criteria (read-only).
- Both:
  - `_app.settings.tsx` — Profile & Settings (tabs/sections).

Persona guard: `_app.tsx` reads session; if none → redirect to `/login`. Individual routes check `session.persona` and redirect to correct dashboard if wrong persona.

Existing `dashboard.tsx` gets removed; existing `/dashboard` redirect handled by new `_app.dashboard.tsx`.

## Components

- `src/components/app-shell/Sidebar.tsx` — logo, 3 nav items (persona-driven), avatar menu at bottom.
- `src/components/app-shell/TopHeader.tsx` — page title + notification bell.
- `src/components/app-shell/NotificationBell.tsx` — popover feed with mark-all-read, invitation Accept/Decline inline.
- `src/components/company/CompanyForm.tsx` — shared form (signup, add, edit). Props: `initial`, `onSubmit`, `submitLabel`, `secondaryAction?` (used by founder signup for "Add later"), `requireCompany` (bool).
- `src/components/founder/FounderCard.tsx`, `FounderScores.tsx`.
- `src/components/memo/Memo.tsx` — verdict card + collapsible sections.

## Files touched

- Edit: `src/lib/api.ts`, `src/routes/signup.tsx`, `src/routes/login.tsx`, `src/routes/__root.tsx` (title only).
- Delete: `src/routes/dashboard.tsx` (replaced by `_app.dashboard.tsx`).
- New: routes above, all new components, `src/lib/mock-data.ts` (large; kept as pure data imported only by `api.ts`).

## Verification

- `tsgo` typecheck.
- Playwright smoke: sign up as investor → Hunt → open a founder → generate memo → send invite; sign up as founder with same email → notification bell shows invite → accept; log back in as investor → notification/status reflects acceptance.

## Out of scope

- Real HTTP calls, real file uploads, real charts library (use simple CSS bars). No auth backend.
