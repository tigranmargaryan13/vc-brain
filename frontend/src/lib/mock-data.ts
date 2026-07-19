// Mock data used by src/lib/api.ts. Only api.ts imports this module.

export type Trend = "up" | "flat" | "down";
export type MarketRating = "Bullish" | "Neutral" | "Bear";
export type FitRating = "Survives as-is" | "Pivot potential" | "At risk";
export type TrustLevel = "High" | "Medium" | "Low";
export type TrustState = "corroborated" | "uncorroborated" | "contradicted";

export type Claim = {
  text: string;
  trust: TrustLevel;
  state: TrustState;
  sourceUrl: string;
  sourceLabel: string;
};

export type EvidenceItem = Claim & { unknown?: boolean };

export type Project = {
  id: string;
  name: string;
  sector: string;
  stage: string;
  oneLiner: string;
};

export type FounderProfile = {
  id: string;
  name: string;
  email: string; // mock — used for invitation delivery
  location: string;
  projects: Project[];
  scores: {
    founder: number; // 0..100
    founderTrend: Trend;
    market: MarketRating;
    marketTrend: Trend;
    fit: FitRating;
    fitTrend: Trend;
  };
  coldStart?: boolean;
  hasContradiction?: boolean;
  evidence: EvidenceItem[];
  memoFor?: Record<string, Memo>; // by project id
};

export type MemoSection = {
  id: string;
  title: string;
  paragraph?: string;
  bullets?: Claim[];
  swot?: { S: Claim[]; W: Claim[]; O: Claim[]; T: Claim[] };
  gaps?: string[];
};

export type MemoVerdict = "Strong yes" | "Conditional yes" | "Watch" | "Pass";

export type Memo = {
  verdict: MemoVerdict;
  scoresRestated: FounderProfile["scores"];
  topReasons: string[];
  sections: MemoSection[];
};

export type Investment = {
  id: string;
  company: string;
  sector: string;
  stage: string;
  amount: number;
  date: string;
  status: "Active" | "Exited" | "Written off";
};

export type CriteriaGroup = {
  id: string;
  label: string;
  weight: number; // 0..100 default
  description: string;
};

export const MOCK_CRITERIA: CriteriaGroup[] = [
  { id: "team", label: "Team", weight: 60, description: "Founder–market fit, prior wins, resilience signals." },
  { id: "traction", label: "Traction", weight: 55, description: "Usage, revenue, retention curves and reference customers." },
  { id: "market", label: "Market", weight: 65, description: "Size, timing, wedge, and defensibility of the beachhead." },
  { id: "product", label: "Product", weight: 50, description: "Insight quality, iteration speed, and technical differentiation." },
];

export const MOCK_INVESTMENTS: Investment[] = [
  { id: "i1", company: "Northwind AI", sector: "AI/ML", stage: "Seed", amount: 500_000, date: "2025-03-14", status: "Active" },
  { id: "i2", company: "Halide Robotics", sector: "Deep Tech", stage: "Pre-seed", amount: 250_000, date: "2025-06-02", status: "Active" },
  { id: "i3", company: "Ledgerlark", sector: "Fintech", stage: "Series A", amount: 1_200_000, date: "2024-11-21", status: "Active" },
  { id: "i4", company: "Verdant Grid", sector: "Climate", stage: "Seed", amount: 400_000, date: "2024-08-09", status: "Active" },
  { id: "i5", company: "Cryoscope", sector: "Biotech", stage: "Pre-seed", amount: 150_000, date: "2024-02-17", status: "Written off" },
];

const src = (label: string) => `https://example.com/source/${encodeURIComponent(label)}`;

// ---------- 10 founder profiles ----------
export const MOCK_FOUNDERS: FounderProfile[] = [
  // 1. FULL-SIGNAL demo
  {
    id: "f_full",
    name: "Priya Ostrander",
    email: "priya@northlake.dev",
    location: "Berlin",
    projects: [
      { id: "p_full_1", name: "Northlake", sector: "AI/ML", stage: "Seed", oneLiner: "Retrieval infra for regulated enterprises." },
    ],
    scores: { founder: 86, founderTrend: "up", market: "Bullish", marketTrend: "up", fit: "Survives as-is", fitTrend: "up" },
    evidence: [
      { text: "Ex-staff engineer, Elastic (5y). Shipped vector indexing subsystem.", trust: "High", state: "corroborated", sourceUrl: src("linkedin"), sourceLabel: "LinkedIn" },
      { text: "3 open-source repos, 4.2k combined stars over 18 months.", trust: "High", state: "corroborated", sourceUrl: src("github"), sourceLabel: "GitHub" },
      { text: "Speaker at KubeCon 2024 on hybrid retrieval.", trust: "Medium", state: "corroborated", sourceUrl: src("kubecon"), sourceLabel: "KubeCon" },
      { text: "6 design partners signed, 2 in EU banking.", trust: "Medium", state: "uncorroborated", sourceUrl: src("founder-update"), sourceLabel: "Founder update" },
    ],
    memoFor: {
      p_full_1: {
        verdict: "Conditional yes",
        scoresRestated: { founder: 86, founderTrend: "up", market: "Bullish", marketTrend: "up", fit: "Survives as-is", fitTrend: "up" },
        topReasons: [
          "Deep, corroborated founder–market fit in retrieval infra.",
          "Timing tailwind: EU AI Act pushes regulated buyers off generic SaaS.",
          "Design-partner list credible; needs signed revenue to fully de-risk.",
        ],
        sections: [
          {
            id: "snapshot",
            title: "Company snapshot",
            bullets: [
              { text: "Northlake builds retrieval infrastructure for regulated enterprises, on-prem or in customer VPC.", trust: "High", state: "corroborated", sourceUrl: src("website"), sourceLabel: "Company site" },
              { text: "Team of 4 in Berlin, all technical.", trust: "High", state: "corroborated", sourceUrl: src("linkedin"), sourceLabel: "LinkedIn" },
            ],
          },
          {
            id: "hypotheses",
            title: "Investment hypotheses",
            bullets: [
              { text: "Regulated buyers will not accept multi-tenant vector DBs — a specialist wins.", trust: "Medium", state: "uncorroborated", sourceUrl: src("analyst"), sourceLabel: "Analyst note" },
              { text: "Ex-Elastic operator can win enterprise trust faster than generalist teams.", trust: "High", state: "corroborated", sourceUrl: src("linkedin"), sourceLabel: "LinkedIn" },
            ],
          },
          {
            id: "swot",
            title: "SWOT",
            swot: {
              S: [{ text: "Domain-native founder; shipped comparable systems at scale.", trust: "High", state: "corroborated", sourceUrl: src("linkedin"), sourceLabel: "LinkedIn" }],
              W: [{ text: "No commercial co-founder; sales motion unproven.", trust: "Medium", state: "corroborated", sourceUrl: src("linkedin"), sourceLabel: "LinkedIn" }],
              O: [{ text: "EU AI Act creates a distinct on-prem retrieval budget line.", trust: "Medium", state: "corroborated", sourceUrl: src("eu-ai-act"), sourceLabel: "EUR-Lex" }],
              T: [{ text: "Hyperscaler bundles could compress pricing at Series B.", trust: "Medium", state: "uncorroborated", sourceUrl: src("analyst"), sourceLabel: "Analyst" }],
            },
          },
          {
            id: "product",
            title: "Problem & product",
            bullets: [
              { text: "Enterprises want RAG without shipping documents to third parties.", trust: "High", state: "corroborated", sourceUrl: src("gartner"), sourceLabel: "Gartner" },
              { text: "Product deploys via Helm chart; ships hybrid BM25+vector out of the box.", trust: "High", state: "corroborated", sourceUrl: src("docs"), sourceLabel: "Docs" },
            ],
          },
          {
            id: "traction",
            title: "Traction & KPIs",
            bullets: [
              { text: "6 design partners; 2 paid pilots at €25k each.", trust: "Medium", state: "uncorroborated", sourceUrl: src("founder-update"), sourceLabel: "Founder update" },
              { text: "Community: 4.2k GitHub stars, 380 Discord members.", trust: "High", state: "corroborated", sourceUrl: src("github"), sourceLabel: "GitHub" },
            ],
          },
          {
            id: "gaps",
            title: "Gaps & due-diligence log",
            gaps: [
              "Cap table: not disclosed.",
              "ARR: founder-reported only; needs Stripe/contract confirmation.",
              "Reference calls with the 2 EU banking partners still to schedule.",
            ],
          },
        ],
      },
    },
  },
  // 2. COLD-START demo
  {
    id: "f_cold",
    name: "Marcus Ede",
    email: "marcus@quietstart.example",
    location: "Lagos",
    projects: [
      { id: "p_cold_1", name: "Quietstart", sector: "Dev Tools", stage: "Pre-seed", oneLiner: "Off-grid CI runners for African teams." },
    ],
    scores: { founder: 58, founderTrend: "up", market: "Neutral", marketTrend: "flat", fit: "Pivot potential", fitTrend: "flat" },
    coldStart: true,
    evidence: [
      { text: "Prior employment", trust: "Low", state: "uncorroborated", sourceUrl: src("unknown"), sourceLabel: "Unknown", unknown: true },
      { text: "Public commits in the last 6 months.", trust: "Medium", state: "corroborated", sourceUrl: src("github-cold"), sourceLabel: "GitHub" },
      { text: "Won regional hackathon (Lagos DevFest 2024).", trust: "Medium", state: "corroborated", sourceUrl: src("devfest"), sourceLabel: "DevFest" },
      { text: "Twitter / public writing", trust: "Low", state: "uncorroborated", sourceUrl: src("unknown"), sourceLabel: "Unknown", unknown: true },
    ],
    memoFor: {
      p_cold_1: {
        verdict: "Watch",
        scoresRestated: { founder: 58, founderTrend: "up", market: "Neutral", marketTrend: "flat", fit: "Pivot potential", fitTrend: "flat" },
        topReasons: [
          "Distinctive wedge in an underserved geography.",
          "Sparse public signal — unknowns not counted against.",
          "Needs a call to convert unknowns into evidence.",
        ],
        sections: [
          {
            id: "snapshot",
            title: "Company snapshot",
            bullets: [
              { text: "Quietstart runs CI on solar-buffered edge hardware placed in African hubs.", trust: "Medium", state: "uncorroborated", sourceUrl: src("website-cold"), sourceLabel: "Landing page" },
            ],
          },
          {
            id: "hypotheses",
            title: "Investment hypotheses",
            bullets: [
              { text: "Reliable, cheap CI is a hard blocker for African dev shops.", trust: "Medium", state: "corroborated", sourceUrl: src("survey"), sourceLabel: "Devs survey" },
            ],
          },
          {
            id: "swot",
            title: "SWOT",
            swot: {
              S: [{ text: "Physically present in the target market.", trust: "Medium", state: "corroborated", sourceUrl: src("devfest"), sourceLabel: "DevFest" }],
              W: [{ text: "Very limited public footprint outside the region.", trust: "High", state: "corroborated", sourceUrl: src("scan"), sourceLabel: "Signal scan" }],
              O: [{ text: "Grants + telco partnerships available for infra pilots.", trust: "Medium", state: "uncorroborated", sourceUrl: src("gsma"), sourceLabel: "GSMA" }],
              T: [{ text: "GitHub Actions edge runners could reach the region first.", trust: "Medium", state: "corroborated", sourceUrl: src("gh-runners"), sourceLabel: "GitHub blog" }],
            },
          },
          { id: "product", title: "Problem & product", paragraph: "Detailed product spec not yet public. Landing page describes the wedge without technical depth." },
          { id: "traction", title: "Traction & KPIs", paragraph: "No public traction metrics." },
          {
            id: "gaps",
            title: "Gaps & due-diligence log",
            gaps: [
              "Founder background: not disclosed.",
              "Team size: unknown.",
              "Revenue / pilots: not disclosed.",
              "Cap table: not disclosed.",
              "Hardware supplier and unit economics: unknown.",
            ],
          },
        ],
      },
    },
  },
  // 3. CONTRADICTION demo
  {
    id: "f_contra",
    name: "Elena Voss",
    email: "elena@brightgrid.example",
    location: "Amsterdam",
    projects: [
      { id: "p_contra_1", name: "Brightgrid", sector: "Climate", stage: "Seed", oneLiner: "Predictive load-balancing for urban microgrids." },
    ],
    scores: { founder: 72, founderTrend: "flat", market: "Bullish", marketTrend: "up", fit: "Survives as-is", fitTrend: "down" },
    hasContradiction: true,
    evidence: [
      { text: "Claims $1.2M ARR (founder deck).", trust: "Low", state: "contradicted", sourceUrl: src("deck"), sourceLabel: "Deck" },
      { text: "Public press: €180k signed pilots to date.", trust: "High", state: "corroborated", sourceUrl: src("press"), sourceLabel: "TechCrunch" },
      { text: "Ex-lead engineer at Alliander (grid operator).", trust: "High", state: "corroborated", sourceUrl: src("linkedin"), sourceLabel: "LinkedIn" },
      { text: "3 city partnerships (The Hague, Utrecht, Rotterdam).", trust: "Medium", state: "corroborated", sourceUrl: src("citypr"), sourceLabel: "City press office" },
    ],
    memoFor: {
      p_contra_1: {
        verdict: "Watch",
        scoresRestated: { founder: 72, founderTrend: "flat", market: "Bullish", marketTrend: "up", fit: "Survives as-is", fitTrend: "down" },
        topReasons: [
          "Real domain expertise and public city partnerships.",
          "Revenue claim contradicts public reporting — reconcile before pricing.",
          "Market direction is right even if this team's execution needs proof.",
        ],
        sections: [
          {
            id: "snapshot",
            title: "Company snapshot",
            bullets: [
              { text: "Brightgrid sells a predictive load-balancing SaaS to municipal grid operators.", trust: "High", state: "corroborated", sourceUrl: src("website"), sourceLabel: "Company site" },
            ],
          },
          {
            id: "hypotheses",
            title: "Investment hypotheses",
            bullets: [
              { text: "Urban microgrids are moving from pilots to procurement over 24 months.", trust: "Medium", state: "corroborated", sourceUrl: src("iea"), sourceLabel: "IEA" },
              { text: "Ex-grid-operator founder wins procurement faster than generic SaaS.", trust: "High", state: "corroborated", sourceUrl: src("linkedin"), sourceLabel: "LinkedIn" },
            ],
          },
          {
            id: "swot",
            title: "SWOT",
            swot: {
              S: [{ text: "Signed municipal partnerships give distribution.", trust: "Medium", state: "corroborated", sourceUrl: src("citypr"), sourceLabel: "City press" }],
              W: [{ text: "Revenue narrative inconsistent across sources.", trust: "Low", state: "contradicted", sourceUrl: src("press"), sourceLabel: "TechCrunch vs deck" }],
              O: [{ text: "EU Green Deal funding is chasing exactly this workload.", trust: "Medium", state: "corroborated", sourceUrl: src("eu"), sourceLabel: "EU Commission" }],
              T: [{ text: "Incumbent SCADA vendors can bolt on similar ML.", trust: "Medium", state: "uncorroborated", sourceUrl: src("analyst"), sourceLabel: "Analyst" }],
            },
          },
          {
            id: "product",
            title: "Problem & product",
            bullets: [
              { text: "Cities lack real-time optimization across DER assets; Brightgrid unifies feeds and forecasts.", trust: "High", state: "corroborated", sourceUrl: src("website"), sourceLabel: "Product page" },
            ],
          },
          {
            id: "traction",
            title: "Traction & KPIs",
            bullets: [
              { text: "Founder deck: $1.2M ARR.", trust: "Low", state: "contradicted", sourceUrl: src("deck"), sourceLabel: "Deck" },
              { text: "Public press: €180k pilot revenue.", trust: "High", state: "corroborated", sourceUrl: src("press"), sourceLabel: "TechCrunch" },
            ],
          },
          {
            id: "gaps",
            title: "Gaps & due-diligence log",
            gaps: [
              "Reconcile ARR claim vs. €180k public figure.",
              "Cap table: partial — angel round undisclosed.",
              "Retention: no cohort data provided.",
            ],
          },
        ],
      },
    },
  },
  // 4-10: additional varied founders (template memos)
  ...(([
    ["f4", "Aiko Marchetti", "aiko@spool.example", "Tokyo", "Spool", "Fintech", "Seed", "Instant treasury for cross-border SMBs.", 74, "up", "Bullish", "up", "Survives as-is", "flat"],
    ["f5", "Rafael Duarte", "rafael@carevein.example", "Lisbon", "Carevein", "Healthtech", "Pre-seed", "Nurse-first EMR for home-visit clinics.", 66, "flat", "Neutral", "flat", "Pivot potential", "up"],
    ["f6", "Nadia Okoro", "nadia@sentrylane.example", "London", "Sentrylane", "Cybersecurity", "Seed", "Autonomous red-team runs for SaaS startups.", 78, "up", "Bullish", "flat", "Survives as-is", "flat"],
    ["f7", "Kai Yamamoto", "kai@fielded.example", "San Francisco", "Fielded", "SaaS", "Series A", "Field-ops platform for solar installers.", 81, "flat", "Bullish", "up", "Survives as-is", "up"],
    ["f8", "Chidera Umeh", "chidera@marrowworks.example", "Nairobi", "Marrowworks", "Biotech", "Pre-seed", "Low-cost bone-marrow HLA typing for African clinics.", 63, "up", "Neutral", "up", "Pivot potential", "up"],
    ["f9", "Léa Bertrand", "lea@stackline.example", "Paris", "Stackline", "Dev Tools", "Seed", "Preview environments as first-class DB citizens.", 70, "up", "Bullish", "flat", "Survives as-is", "flat"],
    ["f10", "Diego Salcedo", "diego@meshroute.example", "Mexico City", "Meshroute", "Deep Tech", "Seed", "Mesh-radio networking for LATAM utilities.", 68, "flat", "Neutral", "flat", "Pivot potential", "flat"],
  ] as const).map(([id, name, email, loc, pname, sector, stage, one, founder, ft, market, mt, fit, fitt]) => ({
    id,
    name,
    email,
    location: loc,
    projects: [{ id: `${id}_p1`, name: pname, sector, stage, oneLiner: one }],
    scores: {
      founder: founder as number,
      founderTrend: ft as Trend,
      market: market as MarketRating,
      marketTrend: mt as Trend,
      fit: fit as FitRating,
      fitTrend: fitt as Trend,
    },
    evidence: [
      { text: `Founded ${pname}. Prior operator experience in ${sector}.`, trust: "High" as TrustLevel, state: "corroborated" as TrustState, sourceUrl: src("linkedin"), sourceLabel: "LinkedIn" },
      { text: `Public roadmap and changelog updated in the last quarter.`, trust: "Medium" as TrustLevel, state: "corroborated" as TrustState, sourceUrl: src("changelog"), sourceLabel: "Changelog" },
      { text: `Cited in one ${sector} landscape report.`, trust: "Medium" as TrustLevel, state: "uncorroborated" as TrustState, sourceUrl: src("report"), sourceLabel: "Landscape report" },
    ],
  }))),
];

export function buildTemplateMemo(f: FounderProfile, p: Project): Memo {
  const claim = (text: string, trust: TrustLevel = "Medium", state: TrustState = "uncorroborated", label = "Signal scan"): Claim => ({
    text, trust, state, sourceUrl: src(label), sourceLabel: label,
  });
  return {
    verdict: f.scores.founder >= 75 ? "Conditional yes" : f.scores.founder >= 60 ? "Watch" : "Pass",
    scoresRestated: f.scores,
    topReasons: [
      `${f.name} shows credible founder–market fit in ${p.sector}.`,
      `Public signals align with the stated wedge, though several claims are uncorroborated.`,
      `Standard diligence items — cap table, revenue, references — remain open.`,
    ],
    sections: [
      { id: "snapshot", title: "Company snapshot", bullets: [claim(`${p.name} — ${p.oneLiner} Based in ${f.location}.`, "High", "corroborated", "Company site")] },
      { id: "hypotheses", title: "Investment hypotheses", bullets: [claim(`${p.sector} at ${p.stage} rewards focused wedges over platform plays.`)] },
      {
        id: "swot",
        title: "SWOT",
        swot: {
          S: [claim(`Domain-relevant founder profile.`, "Medium", "corroborated", "LinkedIn")],
          W: [claim(`Public traction signals are thin.`, "Medium", "uncorroborated")],
          O: [claim(`${p.sector} tailwind visible in recent reports.`, "Medium", "corroborated", "Landscape report")],
          T: [claim(`Adjacent incumbents could compress margin.`)],
        },
      },
      { id: "product", title: "Problem & product", paragraph: `${p.name} targets a specific pain point in ${p.sector}. Product depth to be confirmed on call.` },
      { id: "traction", title: "Traction & KPIs", paragraph: `No public KPI dashboard. Founder-reported metrics only.` },
      { id: "gaps", title: "Gaps & due-diligence log", gaps: ["Cap table: not disclosed.", "Revenue: unverified — founder claim only.", "Reference customers: to be arranged."] },
    ],
  };
}
