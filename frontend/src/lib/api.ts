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
  deckUrl?: string;
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

// ---------- Sourced dataset (fetched from GitHub) ----------
const SOURCED_URL = "https://raw.githubusercontent.com/tigranmargaryan13/vc-brain/ui/data/ui/sourced_founders.json";
let sourcedCache: FounderProfile[] | null = null;
async function loadSourced(): Promise<FounderProfile[]> {
  if (sourcedCache) return sourcedCache;
  try {
    const r = await fetch(SOURCED_URL);
    if (!r.ok) return [];
    const d = await r.json();
    if (!Array.isArray(d)) return [];
    sourcedCache = d.filter((f: FounderProfile) => f && f.id && f.name && Array.isArray(f.projects) && f.scores && Array.isArray(f.evidence));
    return sourcedCache;
  } catch {
    return [];
  }
}
const KNOWN_SECTORS = ["AI/ML", "Fintech", "Climate", "Healthtech", "Dev Tools", "Consumer", "Deep Tech", "Biotech", "Cybersecurity", "SaaS"];

function mapIndustryToSector(industry: string | undefined, other?: string): string {
  const v = (industry === "Other" ? other : industry)?.trim();
  if (!v) return "SaaS";
  const hit = KNOWN_SECTORS.find((s) => s.toLowerCase() === v.toLowerCase());
  return hit ?? v;
}

export function localApplicantProfiles(): FounderProfile[] {
  if (typeof window === "undefined") return [];
  const companies = readJSON<Company[]>(COMPANIES_KEY, []);
  if (!companies.length) return [];
  const users = readUsers();
  const out: FounderProfile[] = [];
  for (const c of companies) {
    const owner = users[userKey(c.ownerEmail, "founder")];
    const displayName = owner?.displayName || c.ownerEmail.split("@")[0];
    const location = c.location || owner?.location || "Unknown";
    const sector = mapIndustryToSector(c.industry, c.otherIndustry);
    const descText = (c.oneLiner || "") + (c.notes ? `\n\n${c.notes}` : "");
    const descLen = descText.length;

    // Dimensions per SCORING.md
    const dims: { name: string; value: number; coverage: number; weight: number }[] = [
      { name: "Capability", value: 0, coverage: 0, weight: 1.3 },
      { name: "Skills", value: 0, coverage: 0, weight: 1.0 },
      { name: "Trajectory", value: 0, coverage: 0, weight: 1.0 },
      { name: "Ceiling", value: 40 + Math.min(40, descLen / 10), coverage: 0.3, weight: 1.5 },
      { name: "Intent", value: 85, coverage: 0.7, weight: 1.2 },
      { name: "Provenance", value: 0, coverage: 0, weight: 0.8 },
      { name: "Traction", value: 0, coverage: 0, weight: 1.0 },
    ];
    let num = 0, den = 0;
    for (const d of dims) {
      num += d.value * d.coverage * d.weight;
      den += d.coverage * d.weight;
    }
    const score = den > 0 ? num / den : 0;
    const avgCov = dims.reduce((s, d) => s + d.coverage, 0) / dims.length;
    const countCov = dims.filter((d) => d.coverage > 0.15).length;
    const confidence = Math.max(0.10, Math.min(0.95, 0.25 + 0.55 * avgCov + 0.04 * countCov));
    const spread = (1 - confidence) * 35;
    const band: [number, number] = [
      Math.max(0, Math.round(score - spread)),
      Math.min(100, Math.round(score + spread)),
    ];

    const evidence: FounderProfile["evidence"] = [
      { text: "Applied in-app with a pitch deck.", trust: "High", state: "corroborated", sourceUrl: "#", sourceLabel: "Application" },
    ];
    if (c.website) {
      evidence.push({ text: `Website: ${c.website}`, trust: "Medium", state: "uncorroborated", sourceUrl: c.website, sourceLabel: "Founder-provided" });
    }
    if (c.oneLiner) {
      evidence.push({ text: c.oneLiner, trust: "Medium", state: "uncorroborated", sourceUrl: "#", sourceLabel: "Founder-provided" });
    }

    const deckAttached = !!(c.deckUrl || c.pitchDeckName);

    const project: Project = {
      id: `p_${c.id}`,
      name: c.name,
      sector,
      stage: "Pre-seed",
      oneLiner: c.oneLiner || "",
      description: descText || undefined,
    };

    const links: { label: string; url: string }[] = [];
    if (c.website) links.push({ label: "Website", url: c.website });

    out.push({
      id: `local_${c.id}`,
      name: displayName,
      email: c.ownerEmail,
      location,
      projects: [project],
      scores: {
        founder: Math.round(score),
        founderTrend: "flat",
        market: "Neutral",
        marketTrend: "flat",
        fit: "Survives as-is",
        fitTrend: "flat",
        confidence,
        band,
      },
      coldStart: true,
      evidence,
      bio: owner?.bio,
      contact: { email: c.ownerEmail, website: c.website },
      dimensions: dims,
      details: {
        source: "In-app application",
        links: links.length ? links : undefined,
      },
      track: "inbound",
      deck: deckAttached
        ? {
            pdfUrl: c.deckUrl,
            notes: c.pitchDeckName ? `Uploaded: ${c.pitchDeckName}` : undefined,
          }
        : undefined,
    });
  }
  return out;
}

async function allFounders(): Promise<FounderProfile[]> {
  return [...MOCK_FOUNDERS, ...(await loadSourced()), ...localApplicantProfiles()];
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
export async function searchFounders(params: {
  q?: string;
  sector?: string;
  stage?: string;
  location?: string;
  savedOnly?: boolean;
}): Promise<FounderProfile[]> {
  let list = (await allFounders()).slice();
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
  const list = await allFounders();
  return delay(list.find((f) => f.id === id) ?? null);
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
  const list = await allFounders();
  const f = list.find((x) => x.id === founderId);
  if (!f) throw new Error("Founder not found.");
  const p = f.projects.find((x) => x.id === projectId) ?? f.projects[0];
  const cacheKey = scopedKey(`${MEMOS_KEY}:${founderId}:${p.id}`, currentSession());
  const cached = readJSON<Memo | null>(cacheKey, null);
  if (cached) return delay(cached, 400);
  const memo = f.memoFor?.[p.id] ?? buildTemplateMemo(f, p);
  writeJSON(cacheKey, memo);
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

export async function countInvitationsForFounder(founderId: string): Promise<number> {
  const all = readJSON<Invitation[]>(INVITES_KEY, []);
  return delay(all.filter((i) => i.founderId === founderId).length);
}

// ---------- Matching ----------
export type MatchReason = { kind: "sector" | "stage" | "geography" | "keyword" | "founder"; label: string };
export type MatchResult = { score: number; reasons: MatchReason[] };

function tokenize(s: string): string[] {
  return (s || "")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length >= 3);
}

export function matchScore(
  founder: FounderProfile,
  thesis: Thesis,
  interests: string[] = [],
): MatchResult {
  const reasons: MatchReason[] = [];
  let score = 0;

  const sectorHit = founder.projects.find((p) => thesis.sectors.includes(p.sector));
  if (sectorHit) { score += 40; reasons.push({ kind: "sector", label: `Sector: ${sectorHit.sector}` }); }

  const stageHit = founder.projects.find((p) => p.stage === thesis.stage);
  if (stageHit) { score += 20; reasons.push({ kind: "stage", label: `Stage: ${stageHit.stage}` }); }

  const geo = thesis.geography?.trim().toLowerCase();
  if (geo && founder.location?.toLowerCase().includes(geo)) {
    score += 10;
    reasons.push({ kind: "geography", label: `Geo: ${founder.location}` });
  }

  const kwTokens = new Set<string>();
  [...thesis.sectors, ...interests].forEach((s) => tokenize(s).forEach((t) => kwTokens.add(t)));
  const haystack = [
    ...founder.projects.map((p) => `${p.description ?? ""} ${p.oneLiner}`),
    ...(founder.skills ?? []),
  ].join(" ").toLowerCase();
  let kwPts = 0;
  const kwSeen: string[] = [];
  for (const t of kwTokens) {
    if (kwPts >= 15) break;
    if (haystack.includes(t)) { kwPts += 3; kwSeen.push(t); }
  }
  if (kwPts > 0) {
    score += Math.min(15, kwPts);
    reasons.push({ kind: "keyword", label: `Keyword: ${kwSeen.slice(0, 2).join(", ")}` });
  }

  const fpts = 15 * (founder.scores.founder / 100);
  score += fpts;
  reasons.push({ kind: "founder", label: `Founder ${founder.scores.founder}` });

  return { score: Math.round(score), reasons };
}

export async function hasThesis(): Promise<boolean> {
  const s = currentSession();
  return readJSON<Thesis | null>(scopedKey(THESIS_KEY, s), null) !== null;
}

export async function listMatchedFounders(): Promise<{ founder: FounderProfile; match: MatchResult }[]> {
  const [list, thesis, user] = await Promise.all([allFounders(), getThesis(), getCurrentUser()]);
  const interests = user?.onboarding?.interests ?? [];
  return list
    .map((f) => ({ founder: f, match: matchScore(f, thesis, interests) }))
    .filter((x) => x.match.score >= 45)
    .sort((a, b) => b.match.score - a.match.score);
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
    const seeds = (await allFounders()).slice(0, 2);
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

// ---------- Natural-language query parser ----------
export type TraitKind =
  | "technical" | "serial" | "traction" | "noVc"
  | "accelerator" | "coldStart" | "researcher" | "inbound";

export type ParsedConstraint =
  | { kind: "sector"; value: string; source: string }
  | { kind: "location"; value: string; source: string }
  | { kind: "stage"; value: string; source: string }
  | { kind: "scoreMin"; value: number; source: string }
  | { kind: "trait"; trait: TraitKind; source: string; exclude?: boolean; bestEffort?: boolean }
  | { kind: "keyword"; value: string };

export type ParsedQuery = { raw: string; constraints: ParsedConstraint[] };

const SECTOR_SYNONYMS: { patterns: RegExp[]; value: string }[] = [
  { value: "AI/ML", patterns: [/\bai\s*infra(structure)?\b/, /\bartificial intelligence\b/, /\bai\/ml\b/, /\bai\b/, /\bml\b/, /\bmachine learning\b/, /\bllm[s]?\b/, /\bagents?\b/] },
  { value: "Dev Tools", patterns: [/\bdev\s*tools?\b/, /\bdevtools?\b/, /\bdeveloper tools?\b/] },
  { value: "Fintech", patterns: [/\bfintech\b/, /\bpayments?\b/, /\bbanking\b/] },
  { value: "Climate", patterns: [/\bclimate\b/, /\benergy\b/, /\bcleantech\b/] },
  { value: "Healthtech", patterns: [/\bhealth(tech)?\b/, /\bmedtech\b/, /\bmedical\b/] },
  { value: "Cybersecurity", patterns: [/\bcyber(security)?\b/, /\bsecurity\b/, /\binfosec\b/] },
  { value: "Deep Tech", patterns: [/\brobotics?\b/, /\bhardware\b/, /\bdeep\s*tech\b/] },
  { value: "Biotech", patterns: [/\bbio(tech)?\b/] },
  { value: "SaaS", patterns: [/\bsaas\b/, /\bb2b\b/] },
  { value: "Consumer", patterns: [/\bconsumer\b/, /\bsocial\b/, /\bb2c\b/] },
];

const PARSER_LOCATIONS = ["Berlin", "London", "Paris", "Amsterdam", "Lisbon", "San Francisco", "New York", "Tokyo", "Nairobi", "Lagos", "Mexico City", "Toronto", "Los Angeles", "Vancouver", "Remote"];

const STAGE_SYNONYMS: { patterns: RegExp[]; value: string }[] = [
  { value: "Pre-seed", patterns: [/\bpre[-\s]?seed\b/] },
  { value: "Series A", patterns: [/\bseries\s*a\b/] },
  { value: "Series B", patterns: [/\bseries\s*b\b/] },
  { value: "Seed", patterns: [/\bseed\b/] },
];

const TECHNICAL_SKILL_RE = /\b(engineer|developer|python|typescript|javascript|react|node|ml|ai|llm|backend|frontend|full.?stack|rust|golang|go|kubernetes|docker|scala|c\+\+|cto|technical|infra|systems)\b/i;

function fragmentToConstraint(frag: string): ParsedConstraint[] {
  const f = frag.trim();
  if (!f) return [];
  const lo = f.toLowerCase();
  const out: ParsedConstraint[] = [];

  const scoreM = lo.match(/score\s*(?:>=|>|above|over|at least|min(?:imum)?)\s*(\d{1,3})/);
  if (scoreM) return [{ kind: "scoreMin", value: Math.min(100, parseInt(scoreM[1], 10)), source: f }];
  if (/\b(strong|top|great|elite)\s+founder\b/.test(lo) || /\bhigh score\b/.test(lo)) {
    out.push({ kind: "scoreMin", value: 70, source: f });
  }

  for (const s of STAGE_SYNONYMS) if (s.patterns.some((p) => p.test(lo))) { out.push({ kind: "stage", value: s.value, source: f }); break; }
  for (const loc of PARSER_LOCATIONS) if (new RegExp(`\\b${loc.toLowerCase()}\\b`).test(lo)) { out.push({ kind: "location", value: loc, source: f }); break; }
  for (const s of SECTOR_SYNONYMS) if (s.patterns.some((p) => p.test(lo))) { out.push({ kind: "sector", value: s.value, source: f }); break; }

  if (/\btechnical founder\b|\bengineer\b|\bbuilder\b/.test(lo)) out.push({ kind: "trait", trait: "technical", source: f });
  if (/\b(serial|repeat)\s+founder\b/.test(lo)) out.push({ kind: "trait", trait: "serial", source: f });
  if (/\btraction\b|\brevenue\b|\bcustomers?\b/.test(lo)) out.push({ kind: "trait", trait: "traction", source: f });
  if (/\b(no|without|zero)\s+(prior\s+)?(vc|venture)(\s*(backing|funding|money))?\b|\bunfunded\b|\bbootstrap(ped)?\b/.test(lo))
    out.push({ kind: "trait", trait: "noVc", source: f, exclude: true, bestEffort: true });
  if (/\btop[-\s]?tier\s+accelerator\b|\byc\b|\by[-\s]?combinator\b|\baccelerator\b|\bincubat/.test(lo))
    out.push({ kind: "trait", trait: "accelerator", source: f });
  if (/\bcold[-\s]?start\b|\bunder the radar\b/.test(lo)) out.push({ kind: "trait", trait: "coldStart", source: f });
  if (/\bresearcher\b|\bacademic\b|\bphd\b|\barxiv\b/.test(lo)) out.push({ kind: "trait", trait: "researcher", source: f });
  if (/\binbound\b|\bapplied\b|\bapplication\b/.test(lo)) out.push({ kind: "trait", trait: "inbound", source: f });

  if (out.length === 0) {
    const cleaned = f.replace(/["]/g, "").trim();
    if (cleaned.length >= 2) out.push({ kind: "keyword", value: cleaned });
  }
  return out;
}

export function parseQuery(q: string): ParsedQuery {
  const raw = (q ?? "").trim();
  if (!raw) return { raw, constraints: [] };
  const frags = raw.split(/,|;|\s+\band\b\s+|\s+\bwith\b\s+|\s*\+\s*/i).map((s) => s.trim()).filter(Boolean);
  const all: ParsedConstraint[] = [];
  for (const frag of frags) all.push(...fragmentToConstraint(frag));
  const seen = new Set<string>();
  const out: ParsedConstraint[] = [];
  for (const c of all) {
    const key =
      c.kind === "trait" ? `trait:${c.trait}` :
      c.kind === "keyword" ? `kw:${c.value.toLowerCase()}` :
      `${c.kind}:${String((c as { value: unknown }).value).toLowerCase()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(c);
  }
  return { raw, constraints: out };
}

function founderHaystack(f: FounderProfile): string {
  return [
    f.name,
    f.bio ?? "",
    (f.skills ?? []).join(" "),
    f.projects.map((p) => `${p.name} ${p.oneLiner} ${p.description ?? ""}`).join(" "),
    f.evidence.map((e) => `${e.text} ${e.sourceLabel}`).join(" "),
    f.details?.source ?? "",
    f.details?.industry ?? "",
  ].join(" ").toLowerCase();
}

function hasTechnicalSignal(f: FounderProfile): boolean {
  if ((f.skills ?? []).some((s) => TECHNICAL_SKILL_RE.test(s))) return true;
  const cap = f.dimensions?.find((d) => /capabil/i.test(d.name));
  if (cap && cap.value >= 60) return true;
  return false;
}

function hasTractionSignal(f: FounderProfile, hay: string): boolean {
  const dim = f.dimensions?.find((d) => /traction/i.test(d.name));
  if (dim && dim.coverage > 0.2) return true;
  if (/\b(traction|revenue|customers?|paying|arr|mrr)\b/.test(hay)) return true;
  if ((f.details?.upvotes ?? 0) >= 50) return true;
  return false;
}

export function applyParsedQuery(founders: FounderProfile[], parsed: ParsedQuery): FounderProfile[] {
  if (!parsed.constraints.length) return founders;
  const sectors = parsed.constraints.flatMap((c) => c.kind === "sector" ? [c.value] : []);
  const stages = parsed.constraints.flatMap((c) => c.kind === "stage" ? [c.value] : []);
  const locations = parsed.constraints.flatMap((c) => c.kind === "location" ? [c.value] : []);
  const scoreMins = parsed.constraints.flatMap((c) => c.kind === "scoreMin" ? [c.value] : []);
  const traits = parsed.constraints.flatMap((c) => c.kind === "trait" ? [c] : []);
  const keywords = parsed.constraints.flatMap((c) => c.kind === "keyword" ? [c.value.toLowerCase()] : []);

  return founders.filter((f) => {
    const hay = founderHaystack(f);
    if (sectors.length && !f.projects.some((p) => sectors.includes(p.sector))) return false;
    if (stages.length && !f.projects.some((p) => stages.includes(p.stage))) return false;
    if (locations.length && !locations.some((loc) => (f.location ?? "").toLowerCase().includes(loc.toLowerCase()))) return false;
    if (scoreMins.length && f.scores.founder < Math.max(...scoreMins)) return false;
    for (const t of traits) {
      const has = (() => {
        switch (t.trait) {
          case "technical": return hasTechnicalSignal(f);
          case "serial": return /\b(serial|repeat|multiple\s+(launches|startups)|shipped\s+multiple|prior\s+(launches|startups))\b/.test(hay);
          case "traction": return hasTractionSignal(f, hay);
          case "noVc": return /\b(raised|funding|funded|investors?|seed round|series [a-c]|venture)\b/.test(hay);
          case "accelerator": return /\b(accelerator|y[-\s]?combinator|yc|incubat|techstars)\b/.test(hay);
          case "coldStart": return !!f.coldStart;
          case "researcher": return (f.details?.source === "Academic sourcing") || (f.details?.source === "arXiv") || /\b(arxiv|researcher|academic|phd)\b/.test(hay);
          case "inbound": return (f.track ?? "outbound") === "inbound";
        }
      })();
      if (t.exclude ? has : !has) return false;
    }
    for (const kw of keywords) if (!hay.includes(kw)) return false;
    return true;
  });
}

export function constraintLabel(c: ParsedConstraint): string {
  switch (c.kind) {
    case "sector": return `Sector: ${c.value}`;
    case "location": return `Location: ${c.value}`;
    case "stage": return `Stage: ${c.value}`;
    case "scoreMin": return `Founder ≥ ${c.value}`;
    case "keyword": return `keyword: "${c.value}"`;
    case "trait": {
      const names: Record<TraitKind, string> = {
        technical: "technical founder", serial: "serial founder", traction: "traction",
        noVc: "VC-backed", accelerator: "accelerator", coldStart: "cold start",
        researcher: "researcher", inbound: "inbound",
      };
      const base = c.exclude ? `Exclude: ${names[c.trait]}` : `Trait: ${names[c.trait]}`;
      return c.bestEffort ? `${base} (best-effort)` : base;
    }
  }
}
