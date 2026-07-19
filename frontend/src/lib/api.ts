// Single API client module. Swap these stubs for real HTTP calls to the
// FastAPI backend later — nothing else in the app should change.
// Nothing outside this file may touch localStorage or mock data.

import {
  MOCK_FOUNDERS,
  MOCK_INVESTMENTS,
  MOCK_CRITERIA,
  buildTemplateMemo,
  type FounderProfile,
  type Memo,
  type Investment,
  type CriteriaGroup,
  type Project,
} from "./mock-data";

export type Persona = "investor" | "founder";

export type OnboardingData = {
  interests: string[];
  otherInterest?: string;
  // Founder-only optional fields (kept for backward compatibility)
  companyName?: string;
  oneLiner?: string;
  website?: string;
  location?: string;
  pitchDeckName?: string;
  notes?: string;
  industry?: string;
  otherIndustry?: string;
};

export type User = {
  email: string;
  persona: Persona;
  displayName?: string;
  bio?: string;
  links?: string;
  location?: string;
  onboarding?: OnboardingData;
  createdAt: string;
};

export type Session = { email: string; persona: Persona };

export type Thesis = {
  sectors: string[];
  stage: string;
  geography: string;
  checkSize: string;
  ownershipTarget: string;
  riskAppetite: string;
  weights: Record<string, number>; // criteria group id -> weight
};

export type Company = {
  id: string;
  ownerEmail: string;
  name: string;
  industry: string;
  otherIndustry?: string;
  pitchDeckName: string;
  website?: string;
  location?: string;
  oneLiner?: string;
  notes?: string;
  createdAt: string;
};

export type Invitation = {
  id: string;
  investorEmail: string;
  founderEmail: string;
  founderId: string; // mock founder profile id OR own account
  projectId?: string;
  message: string;
  status: "sent" | "accepted" | "declined";
  createdAt: string;
};

export type Notification = {
  id: string;
  kind: "best_match" | "invitation" | "invitation_response";
  title: string;
  body: string;
  createdAt: string;
  read: boolean;
  // routing / actions
  founderId?: string;
  invitationId?: string;
};

export type NotificationPrefs = {
  bestMatchAlerts: boolean;
  invitations: boolean;
  emailDigest: boolean;
};

// ---------- storage keys ----------
const USERS_KEY = "vcbrain.users";
const SESSION_KEY = "vcbrain.session";
const THESIS_KEY = "vcbrain.thesis"; // per user
const SAVED_KEY = "vcbrain.saved"; // per investor
const COMPANIES_KEY = "vcbrain.companies";
const INVITES_KEY = "vcbrain.invitations";
const READ_NOTIFS_KEY = "vcbrain.readNotifs"; // per user set of ids
const PREFS_KEY = "vcbrain.prefs";
const MEMOS_KEY = "vcbrain.memos";

type StoredUser = User & { password: string };

// ---------- helpers ----------
function readJSON<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}
function writeJSON(key: string, value: unknown) {
  if (typeof window === "undefined") return;
  localStorage.setItem(key, JSON.stringify(value));
}
function delay<T>(v: T, ms = 200): Promise<T> {
  return new Promise((r) => setTimeout(() => r(v), ms));
}
function userKey(email: string, persona: Persona) {
  return `${email.trim().toLowerCase()}::${persona}`;
}
function readUsers(): Record<string, StoredUser> {
  return readJSON<Record<string, StoredUser>>(USERS_KEY, {});
}
function writeUsers(u: Record<string, StoredUser>) {
  writeJSON(USERS_KEY, u);
}
function stripPw(u: StoredUser): User {
  const { password: _pw, ...safe } = u;
  return safe;
}
function currentSession(): Session | null {
  const raw = typeof window === "undefined" ? null : localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const s = JSON.parse(raw);
    if (s && s.email && s.persona) return s as Session;
  } catch {
    // legacy: raw email string
    if (typeof raw === "string" && raw.includes("@")) {
      return { email: raw, persona: "investor" };
    }
  }
  return null;
}
function scopedKey(base: string, session: Session | null) {
  if (!session) return base;
  return `${base}:${session.email}:${session.persona}`;
}

// ---------- Auth ----------
export async function completeSignUp(params: {
  email: string;
  password: string;
  persona: Persona;
  onboarding: OnboardingData;
}): Promise<User> {
  const email = params.email.trim().toLowerCase();
  const users = readUsers();
  const key = userKey(email, params.persona);
  if (users[key]) {
    throw new Error(`An ${params.persona} account with this email already exists.`);
  }
  const otherKey = userKey(email, params.persona === "investor" ? "founder" : "investor");
  const noteOther = users[otherKey]
    ? ` (You already have a ${params.persona === "investor" ? "founder" : "investor"} account with this email — that's fine, they're separate.)`
    : "";
  const user: StoredUser = {
    email,
    password: params.password,
    persona: params.persona,
    displayName: email.split("@")[0],
    onboarding: params.onboarding,
    createdAt: new Date().toISOString(),
  };
  users[key] = user;
  writeUsers(users);
  writeJSON(SESSION_KEY, { email, persona: params.persona });
  // Inbound bridge: a founder who supplied company details at signup enters the funnel.
  const ob = params.onboarding;
  if (params.persona === "founder" && ob.companyName) {
    void submitApplication({
      name: user.displayName,
      company: ob.companyName,
      one_liner: ob.oneLiner,
      website: ob.website,
      location: ob.location,
      industry: ob.industry === "Other" ? ob.otherIndustry || "" : ob.industry,
      notes: ob.notes,
    });
  }
  // Note is informational only — do not throw. Consumers can ignore.
  void noteOther;
  return delay(stripPw(user));
}

export async function logIn(params: {
  email: string;
  password: string;
  persona: Persona;
}): Promise<User> {
  const email = params.email.trim().toLowerCase();
  const users = readUsers();
  const key = userKey(email, params.persona);
  const u = users[key];
  if (!u) {
    const otherPersona = params.persona === "investor" ? "founder" : "investor";
    const otherKey = userKey(email, otherPersona);
    if (users[otherKey]) {
      throw new Error(
        `No ${params.persona} account for this email — did you mean to log in as a ${otherPersona}?`,
      );
    }
    throw new Error("Invalid email or password.");
  }
  if (u.password !== params.password) {
    throw new Error("Invalid email or password.");
  }
  writeJSON(SESSION_KEY, { email, persona: params.persona });
  return delay(stripPw(u));
}

export async function getCurrentUser(): Promise<User | null> {
  const s = currentSession();
  if (!s) return null;
  const users = readUsers();
  const u = users[userKey(s.email, s.persona)];
  return u ? stripPw(u) : null;
}

export async function logOut(): Promise<void> {
  if (typeof window !== "undefined") localStorage.removeItem(SESSION_KEY);
}

export async function updateProfile(patch: Partial<Pick<User, "displayName" | "bio" | "links" | "location" | "onboarding">>): Promise<User> {
  const s = currentSession();
  if (!s) throw new Error("Not signed in.");
  const users = readUsers();
  const k = userKey(s.email, s.persona);
  const u = users[k];
  if (!u) throw new Error("Session invalid.");
  Object.assign(u, patch);
  users[k] = u;
  writeUsers(users);
  return delay(stripPw(u));
}

export async function changePassword(params: { current: string; next: string }): Promise<void> {
  const s = currentSession();
  if (!s) throw new Error("Not signed in.");
  const users = readUsers();
  const k = userKey(s.email, s.persona);
  const u = users[k];
  if (!u || u.password !== params.current) throw new Error("Current password is incorrect.");
  if (params.next.length < 8) throw new Error("New password must be at least 8 characters.");
  u.password = params.next;
  users[k] = u;
  writeUsers(users);
  return delay(undefined);
}

export async function deleteAccount(): Promise<void> {
  const s = currentSession();
  if (!s) return;
  const users = readUsers();
  delete users[userKey(s.email, s.persona)];
  writeUsers(users);
  localStorage.removeItem(SESSION_KEY);
  return delay(undefined);
}

// ---------- Notification prefs ----------
const DEFAULT_PREFS: NotificationPrefs = {
  bestMatchAlerts: true,
  invitations: true,
  emailDigest: false,
};
export async function getNotificationPrefs(): Promise<NotificationPrefs> {
  const s = currentSession();
  return delay(readJSON<NotificationPrefs>(scopedKey(PREFS_KEY, s), DEFAULT_PREFS));
}
export async function updateNotificationPrefs(next: NotificationPrefs): Promise<NotificationPrefs> {
  const s = currentSession();
  writeJSON(scopedKey(PREFS_KEY, s), next);
  return delay(next);
}

// ---------- Investor: founders / hunt ----------
// --- real backend (FastAPI over the sourcing pipeline); falls back to mock if offline ---
const API_URL = (import.meta as any).env?.VITE_API_URL || "http://localhost:8000";

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return (await res.json()) as T;
}

// A founder application, as the pipeline's POST /api/apply expects it.
export type Application = {
  name?: string;
  company?: string;
  one_liner?: string;
  website?: string;
  location?: string;
  github?: string;
  industry?: string;
  stage?: string;
  notes?: string;
};

// Inbound bridge: push a founder's own application INTO the scoring pipeline, so
// they enter the same funnel as outbound-discovered founders (source_track=inbound).
// Best-effort and never throws — if the backend is offline the local flow is unaffected.
export async function submitApplication(app: Application): Promise<FounderProfile | null> {
  try {
    const res = await fetch(`${API_URL}/api/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(app),
    });
    if (!res.ok) return null;
    return (await res.json()) as FounderProfile;
  } catch {
    return null; // backend offline -> stays a local-only account
  }
}

export async function searchFounders(params: {
  q?: string;
  sector?: string;
  stage?: string;
  location?: string;
  savedOnly?: boolean;
}): Promise<FounderProfile[]> {
  let list: FounderProfile[];
  try {
    list = await apiGet<FounderProfile[]>("/api/founders?limit=200");
  } catch {
    list = MOCK_FOUNDERS.slice(); // backend offline -> mock fallback
  }
  const q = params.q?.trim().toLowerCase();
  if (q) {
    list = list.filter(
      (f) =>
        f.name.toLowerCase().includes(q) ||
        f.projects.some(
          (p) => p.name.toLowerCase().includes(q) || p.oneLiner.toLowerCase().includes(q),
        ),
    );
  }
  if (params.sector && params.sector !== "all") {
    list = list.filter((f) => f.projects.some((p) => p.sector === params.sector));
  }
  if (params.stage && params.stage !== "all") {
    list = list.filter((f) => f.projects.some((p) => p.stage === params.stage));
  }
  if (params.location && params.location !== "all") {
    list = list.filter((f) => f.location === params.location);
  }
  if (params.savedOnly) {
    const saved = await listSaved();
    list = list.filter((f) => saved.includes(f.id));
  }
  return delay(list);
}

export async function getFounder(id: string): Promise<FounderProfile | null> {
  try {
    return await apiGet<FounderProfile>(`/api/founders/${encodeURIComponent(id)}`);
  } catch {
    return delay(MOCK_FOUNDERS.find((f) => f.id === id) ?? null); // offline / not found -> mock
  }
}

export async function listSaved(): Promise<string[]> {
  const s = currentSession();
  return readJSON<string[]>(scopedKey(SAVED_KEY, s), []);
}
export async function saveProject(founderId: string): Promise<string[]> {
  const s = currentSession();
  const cur = readJSON<string[]>(scopedKey(SAVED_KEY, s), []);
  if (!cur.includes(founderId)) cur.push(founderId);
  writeJSON(scopedKey(SAVED_KEY, s), cur);
  return delay(cur);
}
export async function unsaveProject(founderId: string): Promise<string[]> {
  const s = currentSession();
  const cur = readJSON<string[]>(scopedKey(SAVED_KEY, s), []).filter((x) => x !== founderId);
  writeJSON(scopedKey(SAVED_KEY, s), cur);
  return delay(cur);
}

export async function generateMemo(founderId: string, projectId: string): Promise<Memo> {
  // Real memo from the backend (already produced by the scoring pipeline).
  try {
    const bf = await apiGet<FounderProfile>(`/api/founders/${encodeURIComponent(founderId)}`);
    const memo = bf.memoFor?.[projectId] ?? Object.values(bf.memoFor ?? {})[0];
    if (memo) return delay(memo, 300);
  } catch {
    /* backend offline -> mock fallback below */
  }
  const f = MOCK_FOUNDERS.find((x) => x.id === founderId);
  if (!f) throw new Error("Founder not found.");
  const p = f.projects.find((x) => x.id === projectId) ?? f.projects[0];
  const memo = f.memoFor?.[p.id] ?? buildTemplateMemo(f, p);
  return delay(memo, 900);
}

// ---------- Investor: investments (portfolio) ----------
export async function listInvestments(): Promise<Investment[]> {
  return delay(MOCK_INVESTMENTS);
}

// ---------- Thesis / Criteria ----------
export async function getCriteria(): Promise<CriteriaGroup[]> {
  return delay(MOCK_CRITERIA);
}
export async function getThesis(): Promise<Thesis> {
  const s = currentSession();
  const cached = readJSON<Thesis | null>(scopedKey(THESIS_KEY, s), null);
  if (cached) return delay(cached);
  // seed from onboarding interests
  const u = await getCurrentUser();
  const interests = u?.onboarding?.interests ?? [];
  const sectors = interests.filter((i) =>
    ["AI/ML", "Fintech", "Climate", "Healthtech", "Dev Tools", "Consumer", "Deep Tech", "Biotech", "Cybersecurity", "SaaS"].includes(i),
  );
  const stage = interests.find((i) => ["Pre-seed", "Seed", "Series A"].includes(i)) ?? "Pre-seed";
  const weights: Record<string, number> = {};
  MOCK_CRITERIA.forEach((g) => (weights[g.id] = 50));
  return delay({
    sectors,
    stage,
    geography: "",
    checkSize: "",
    ownershipTarget: "",
    riskAppetite: "Balanced",
    weights,
  });
}
export async function saveThesis(t: Thesis): Promise<Thesis> {
  const s = currentSession();
  writeJSON(scopedKey(THESIS_KEY, s), t);
  return delay(t);
}

// ---------- Founder: companies ----------
export async function listCompanies(): Promise<Company[]> {
  const s = currentSession();
  if (!s) return [];
  return delay(readJSON<Company[]>(COMPANIES_KEY, []).filter((c) => c.ownerEmail === s.email));
}
export async function getCompany(id: string): Promise<Company | null> {
  const all = readJSON<Company[]>(COMPANIES_KEY, []);
  return delay(all.find((c) => c.id === id) ?? null);
}
export async function addCompany(input: Omit<Company, "id" | "ownerEmail" | "createdAt">): Promise<Company> {
  const s = currentSession();
  if (!s) throw new Error("Not signed in.");
  const all = readJSON<Company[]>(COMPANIES_KEY, []);
  const c: Company = {
    ...input,
    id: `co_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    ownerEmail: s.email,
    createdAt: new Date().toISOString(),
  };
  all.push(c);
  writeJSON(COMPANIES_KEY, all);
  // Inbound bridge: a founder registering their startup enters the scoring funnel.
  const applicant = readUsers()[userKey(s.email, "founder")];
  void submitApplication({
    name: applicant?.displayName || s.email.split("@")[0],
    company: c.name,
    one_liner: c.oneLiner,
    website: c.website,
    location: c.location,
    industry: c.industry === "Other" ? c.otherIndustry || "" : c.industry,
    notes: c.notes,
  });
  return delay(c);
}
export async function updateCompany(id: string, patch: Partial<Omit<Company, "id" | "ownerEmail" | "createdAt">>): Promise<Company> {
  const all = readJSON<Company[]>(COMPANIES_KEY, []);
  const idx = all.findIndex((c) => c.id === id);
  if (idx < 0) throw new Error("Company not found.");
  all[idx] = { ...all[idx], ...patch };
  writeJSON(COMPANIES_KEY, all);
  return delay(all[idx]);
}

// ---------- Founder: stats ----------
export async function listFounderStats(): Promise<{
  shortlisted: number;
  profileViews: number;
  invitations: number;
  accepted: number;
  declined: number;
  byProject: { name: string; views: number; saves: number }[];
}> {
  const s = currentSession();
  const invites = readJSON<Invitation[]>(INVITES_KEY, []).filter(
    (i) => i.founderEmail === s?.email,
  );
  const companies = await listCompanies();
  return delay({
    shortlisted: 12 + invites.length,
    profileViews: 84 + invites.length * 5,
    invitations: invites.length,
    accepted: invites.filter((i) => i.status === "accepted").length,
    declined: invites.filter((i) => i.status === "declined").length,
    byProject: (companies.length ? companies : [{ name: "Your first company" } as Company]).map((c, i) => ({
      name: c.name,
      views: 30 + i * 12,
      saves: 4 + i * 2,
    })),
  });
}

// ---------- Invitations ----------
export async function sendInvitation(params: {
  founderId: string;
  founderEmail: string;
  projectId?: string;
  message: string;
}): Promise<Invitation> {
  const s = currentSession();
  if (!s) throw new Error("Not signed in.");
  const all = readJSON<Invitation[]>(INVITES_KEY, []);
  if (all.find((i) => i.investorEmail === s.email && i.founderId === params.founderId && i.status === "sent")) {
    throw new Error("Invitation already sent.");
  }
  const inv: Invitation = {
    id: `inv_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    investorEmail: s.email,
    founderEmail: params.founderEmail.trim().toLowerCase(),
    founderId: params.founderId,
    projectId: params.projectId,
    message: params.message,
    status: "sent",
    createdAt: new Date().toISOString(),
  };
  all.push(inv);
  writeJSON(INVITES_KEY, all);
  return delay(inv);
}

export async function listInvitationsForInvestor(): Promise<Invitation[]> {
  const s = currentSession();
  if (!s) return [];
  return delay(readJSON<Invitation[]>(INVITES_KEY, []).filter((i) => i.investorEmail === s.email));
}

export async function respondToInvitation(id: string, action: "accept" | "decline"): Promise<Invitation> {
  const all = readJSON<Invitation[]>(INVITES_KEY, []);
  const idx = all.findIndex((i) => i.id === id);
  if (idx < 0) throw new Error("Invitation not found.");
  all[idx].status = action === "accept" ? "accepted" : "declined";
  writeJSON(INVITES_KEY, all);
  return delay(all[idx]);
}

// ---------- Notifications ----------
export async function listNotifications(): Promise<Notification[]> {
  const s = currentSession();
  if (!s) return [];
  const readSet = new Set(readJSON<string[]>(scopedKey(READ_NOTIFS_KEY, s), []));
  const out: Notification[] = [];
  const invites = readJSON<Invitation[]>(INVITES_KEY, []);

  if (s.persona === "founder") {
    for (const inv of invites.filter((i) => i.founderEmail === s.email)) {
      out.push({
        id: `n_inv_${inv.id}`,
        kind: "invitation",
        title: `New invitation from ${inv.investorEmail}`,
        body: inv.message,
        createdAt: inv.createdAt,
        read: readSet.has(`n_inv_${inv.id}`) || inv.status !== "sent",
        invitationId: inv.id,
      });
    }
  } else {
    // Investor: best-match alerts (mocked from thesis) + invitation responses
    for (const inv of invites.filter((i) => i.investorEmail === s.email && i.status !== "sent")) {
      out.push({
        id: `n_resp_${inv.id}`,
        kind: "invitation_response",
        title: `${inv.founderEmail} ${inv.status} your invitation`,
        body: `Regarding project ${inv.projectId ?? ""}`.trim(),
        createdAt: new Date().toISOString(),
        read: readSet.has(`n_resp_${inv.id}`),
        founderId: inv.founderId,
        invitationId: inv.id,
      });
    }
    // Two seeded best-match alerts referencing mock founders
    const thesis = await getThesis();
    const sectorLabel = thesis.sectors[0] ?? "AI/ML";
    const seeds = MOCK_FOUNDERS.slice(0, 2);
    for (const f of seeds) {
      const nid = `n_match_${f.id}`;
      out.push({
        id: nid,
        kind: "best_match",
        title: `Matches your thesis: ${sectorLabel} · ${thesis.stage} · ${f.location}`,
        body: `${f.name} — ${f.projects[0].oneLiner}`,
        createdAt: new Date(Date.now() - 3600_000).toISOString(),
        read: readSet.has(nid),
        founderId: f.id,
      });
    }
  }
  out.sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
  return delay(out, 100);
}

export async function markNotificationRead(id: string): Promise<void> {
  const s = currentSession();
  const cur = new Set(readJSON<string[]>(scopedKey(READ_NOTIFS_KEY, s), []));
  cur.add(id);
  writeJSON(scopedKey(READ_NOTIFS_KEY, s), Array.from(cur));
  return delay(undefined, 50);
}
export async function markAllNotificationsRead(): Promise<void> {
  const s = currentSession();
  const all = await listNotifications();
  writeJSON(scopedKey(READ_NOTIFS_KEY, s), all.map((n) => n.id));
  return delay(undefined, 50);
}

// Re-export types consumers need
export type { FounderProfile, Project, Memo, Investment, CriteriaGroup } from "./mock-data";
