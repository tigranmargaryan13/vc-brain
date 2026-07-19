import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { FounderCard } from "@/components/founder-card";
import {
  searchFounders, listSaved, saveProject, unsaveProject, listInvitationsForInvestor,
  sendInvitation, getCurrentUser, listMatchedFounders, hasThesis,
  parseQuery, applyParsedQuery, constraintLabel,
  type FounderProfile, type Invitation, type User, type MatchResult, type ParsedConstraint,
} from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Plus, X } from "lucide-react";

export const Route = createFileRoute("/_authenticated/hunt")({
  component: HuntPage,
});

const SECTORS = ["all", "AI/ML", "Fintech", "Climate", "Healthtech", "Dev Tools", "Consumer", "Deep Tech", "Biotech", "Cybersecurity", "SaaS", "Unknown"];
const STAGES = ["all", "Pre-seed", "Seed", "Series A", "Series B", "Unknown"];
const LOCATIONS = ["all", "Berlin", "London", "Paris", "Amsterdam", "Lisbon", "San Francisco", "New York", "Tokyo", "Nairobi", "Lagos", "Mexico City", "Toronto", "Los Angeles", "Vancouver", "Remote", "Unknown"];

const MARKET_OPTIONS = ["Bullish", "Neutral", "Bear"] as const;
const FIT_OPTIONS = ["Survives as-is", "Pivot potential", "At risk"] as const;
const SOURCE_OPTIONS = ["Product Hunt", "NYC founders dinner", "Academic sourcing", "arXiv", "Other"] as const;

type ExtraKey = "market" | "fit" | "source" | "coldStart" | "contradiction" | "completenessMin" | "confidenceMin" | "skills";
const EXTRA_LABELS: Record<ExtraKey, string> = {
  market: "Market stance",
  fit: "Idea vs. Market",
  source: "Source",
  coldStart: "Cold start",
  contradiction: "Contradiction",
  completenessMin: "Completeness (min)",
  confidenceMin: "Confidence (min)",
  skills: "Skills",
};

type ExtraState = {
  market?: typeof MARKET_OPTIONS[number];
  fit?: typeof FIT_OPTIONS[number];
  source?: string;
  coldStart?: "only" | "exclude";
  contradiction?: "only" | "exclude";
  completenessMin?: number;
  confidenceMin?: number;
  skills?: string[];
};

const STATE_KEY = "vcbrain.huntState";
type View = "all" | "saved" | "matched";
type Tab = "inbound" | "outbound";

// Compact reusable Select trigger styling
const compactTrigger = "h-8 text-xs";

function HuntPage() {
  const [user, setUser] = useState<User | null>(null);
  const [tab, setTab] = useState<Tab>("inbound");
  const [q, setQ] = useState("");
  const [sector, setSector] = useState("all");
  const [stage, setStage] = useState("all");
  const [loc, setLoc] = useState("all");
  const [founderMin, setFounderMin] = useState(0);
  const [view, setView] = useState<View>("all");
  const [extras, setExtras] = useState<ExtraState>({});
  const [visibleExtras, setVisibleExtras] = useState<ExtraKey[]>([]);
  const [results, setResults] = useState<FounderProfile[]>([]);
  const [matches, setMatches] = useState<Record<string, MatchResult>>({});
  const [thesisSet, setThesisSet] = useState(true);
  const [saved, setSaved] = useState<string[]>([]);
  const [invites, setInvites] = useState<Invitation[]>([]);
  const [inviteFor, setInviteFor] = useState<FounderProfile | null>(null);
  const [inviteMsg, setInviteMsg] = useState("");
  const [dismissedKeys, setDismissedKeys] = useState<string[]>([]);

  const parsed = useMemo(() => parseQuery(q), [q]);
  const ckey = (c: ParsedConstraint) =>
    c.kind === "trait" ? `trait:${c.trait}`
    : c.kind === "keyword" ? `kw:${c.value.toLowerCase()}`
    : `${c.kind}:${String((c as { value: unknown }).value).toLowerCase()}`;
  const activeConstraints = useMemo(
    () => parsed.constraints.filter((c) => !dismissedKeys.includes(ckey(c))),
    [parsed, dismissedKeys],
  );
  const activeParsed = useMemo(() => ({ raw: parsed.raw, constraints: activeConstraints }), [parsed.raw, activeConstraints]);
  // reset dismissals when the raw query text changes
  useEffect(() => { setDismissedKeys([]); }, [q]);

  // Parsed overrides for structured filters
  const parsedSector = activeConstraints.find((c) => c.kind === "sector") as { value: string } | undefined;
  const parsedStage = activeConstraints.find((c) => c.kind === "stage") as { value: string } | undefined;
  const parsedLoc = activeConstraints.find((c) => c.kind === "location") as { value: string } | undefined;
  const effSector = parsedSector?.value ?? sector;
  const effStage = parsedStage?.value ?? stage;
  const effLoc = parsedLoc?.value ?? loc;
  // if we have any parsed constraints, defer text matching to applyParsedQuery (haystack)
  const effQ = activeConstraints.length ? undefined : q;

  useEffect(() => {
    getCurrentUser().then(setUser);
    hasThesis().then(setThesisSet);
    try {
      const raw = sessionStorage.getItem(STATE_KEY);
      if (raw) {
        const s = JSON.parse(raw);
        setTab(s.tab ?? "inbound");
        setQ(s.q ?? ""); setSector(s.sector ?? "all"); setStage(s.stage ?? "all"); setLoc(s.loc ?? "all"); setView(s.view ?? "all");
        setFounderMin(s.founderMin ?? 0);
        setExtras(s.extras ?? {});
        setVisibleExtras(s.visibleExtras ?? []);
        setTimeout(() => window.scrollTo(0, s.scroll ?? 0), 50);
      }
    } catch {}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    sessionStorage.setItem(STATE_KEY, JSON.stringify({ tab, q, sector, stage, loc, view, founderMin, extras, visibleExtras, scroll: window.scrollY }));
  }, [tab, q, sector, stage, loc, view, founderMin, extras, visibleExtras]);

  async function refresh() {
    if (view === "matched") {
      const [m, s, i] = await Promise.all([listMatchedFounders(), listSaved(), listInvitationsForInvestor()]);
      const map: Record<string, MatchResult> = {};
      m.forEach((x) => { map[x.founder.id] = x.match; });
      setMatches(map);
      setResults(m.map((x) => x.founder));
      setSaved(s); setInvites(i);
      return;
    }
    const [r, s, i] = await Promise.all([
      searchFounders({ q: effQ, sector: effSector, stage: effStage, location: effLoc, savedOnly: view === "saved" }),
      listSaved(),
      listInvitationsForInvestor(),
    ]);
    setMatches({});
    const sorted = [...r].sort((a, b) => {
      const ac = a.completeness ?? -1;
      const bc = b.completeness ?? -1;
      if (bc !== ac) return bc - ac;
      return b.scores.founder - a.scores.founder;
    });
    setResults(sorted); setSaved(s); setInvites(i);
  }
  useEffect(() => { void refresh(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [effQ, effSector, effStage, effLoc, view]);

  // Client-side filtering by tab + extras + founderMin + parsed traits/keywords
  const filtered = useMemo(() => {
    let list = results.filter((f) => (f.track ?? "outbound") === tab);
    if (founderMin > 0) list = list.filter((f) => f.scores.founder >= founderMin);
    if (extras.market) list = list.filter((f) => f.scores.market === extras.market);
    if (extras.fit) list = list.filter((f) => f.scores.fit === extras.fit);
    if (extras.source) {
      list = list.filter((f) => {
        const s = f.details?.source;
        if (extras.source === "Other") return s ? !(SOURCE_OPTIONS as readonly string[]).slice(0, -1).includes(s) : false;
        return s === extras.source;
      });
    }
    if (extras.coldStart === "only") list = list.filter((f) => f.coldStart);
    if (extras.coldStart === "exclude") list = list.filter((f) => !f.coldStart);
    if (extras.contradiction === "only") list = list.filter((f) => f.hasContradiction);
    if (extras.contradiction === "exclude") list = list.filter((f) => !f.hasContradiction);
    if (extras.completenessMin != null) list = list.filter((f) => (f.completeness ?? 0) >= extras.completenessMin!);
    if (extras.confidenceMin != null) list = list.filter((f) => ((f.scores.confidence ?? 0) * 100) >= extras.confidenceMin!);
    if (extras.skills?.length) {
      const need = new Set(extras.skills.map((s) => s.toLowerCase()));
      list = list.filter((f) => (f.skills ?? []).some((s) => need.has(s.toLowerCase())));
    }
    // Parsed NL constraints (traits/keywords + reassert overrides against results)
    list = applyParsedQuery(list, activeParsed);
    return list;
  }, [results, tab, founderMin, extras, activeParsed]);


  const allSkills = useMemo(() => {
    const set = new Set<string>();
    results.forEach((f) => (f.skills ?? []).forEach((s) => set.add(s)));
    return Array.from(set).sort();
  }, [results]);

  const inviteByFounder = useMemo(() => {
    const m: Record<string, Invitation> = {};
    invites.forEach((i) => { m[i.founderId] = i; });
    return m;
  }, [invites]);

  async function toggleSave(f: FounderProfile) {
    if (saved.includes(f.id)) { setSaved(await unsaveProject(f.id)); toast("Removed from saved."); }
    else { setSaved(await saveProject(f.id)); toast.success("Saved."); }
  }

  function openInvite(f: FounderProfile) {
    setInviteFor(f);
    setInviteMsg(
      `Hi ${f.name.split(" ")[0]},\n\nWe came across ${f.projects[0].name} and it aligns with what we're actively backing at ${f.projects[0].stage} in ${f.projects[0].sector}. Would you be open to a short intro call?\n\n— ${user?.displayName ?? user?.email ?? "the team"}`,
    );
  }

  async function sendInvite() {
    if (!inviteFor) return;
    try {
      await sendInvitation({
        founderId: inviteFor.id,
        founderEmail: inviteFor.email,
        projectId: inviteFor.projects[0].id,
        message: inviteMsg,
      });
      toast.success("Invitation sent.");
      setInviteFor(null);
      await refresh();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to send.");
    }
  }

  function addExtra(k: ExtraKey) {
    if (visibleExtras.includes(k)) return;
    setVisibleExtras([...visibleExtras, k]);
    const defaults: Partial<ExtraState> = {
      completenessMin: 50, confidenceMin: 50,
      market: "Bullish", fit: "Survives as-is", source: "Product Hunt",
      coldStart: "only", contradiction: "only", skills: [],
    };
    if (extras[k] == null) setExtras((e) => ({ ...e, [k]: defaults[k] as never }));
  }
  function removeExtra(k: ExtraKey) {
    setVisibleExtras(visibleExtras.filter((x) => x !== k));
    setExtras((e) => { const n = { ...e }; delete n[k]; return n; });
  }
  function patchExtra<K extends ExtraKey>(k: K, v: ExtraState[K]) {
    setExtras((e) => ({ ...e, [k]: v }));
  }

  const availableExtras = (Object.keys(EXTRA_LABELS) as ExtraKey[]).filter((k) => !visibleExtras.includes(k));

  const activeChips: { label: string; onRemove: () => void }[] = [];
  if (sector !== "all") activeChips.push({ label: `Sector: ${sector}`, onRemove: () => setSector("all") });
  if (stage !== "all") activeChips.push({ label: `Stage: ${stage}`, onRemove: () => setStage("all") });
  if (loc !== "all") activeChips.push({ label: `Location: ${loc}`, onRemove: () => setLoc("all") });
  if (founderMin > 0) activeChips.push({ label: `Founder ≥ ${founderMin}`, onRemove: () => setFounderMin(0) });
  visibleExtras.forEach((k) => {
    const v = extras[k];
    if (v == null || (Array.isArray(v) && v.length === 0)) return;
    const val = Array.isArray(v) ? v.join(", ") : String(v);
    activeChips.push({ label: `${EXTRA_LABELS[k]}: ${val}`, onRemove: () => removeExtra(k) });
  });

  const tabCounts = useMemo(() => {
    const inbound = results.filter((f) => (f.track ?? "outbound") === "inbound").length;
    const outbound = results.filter((f) => (f.track ?? "outbound") === "outbound").length;
    return { inbound, outbound };
  }, [results]);

  return (
    <AppShell title="Hunt Founders">
      <div className="space-y-6">
        {/* Inbound / Outbound tabs */}
        <div className="inline-flex rounded-lg border border-border/60 bg-surface-elevated/60 p-1">
          {(["inbound", "outbound"] as const).map((k) => (
            <button
              key={k}
              onClick={() => setTab(k)}
              className={cn(
                "rounded-md px-4 py-1.5 text-sm font-medium capitalize transition",
                tab === k ? "bg-gradient-brand text-primary-foreground shadow-glow" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {k} ({k === "inbound" ? tabCounts.inbound : tabCounts.outbound})
            </button>
          ))}
        </div>

        {/* Filters block */}
        <div className="rounded-2xl border border-border/60 bg-surface/60 p-4 backdrop-blur">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-display text-sm font-semibold uppercase tracking-widest text-muted-foreground">Filters</h3>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm" variant="outline" disabled={!availableExtras.length}>
                  <Plus className="mr-1 h-3.5 w-3.5" /> Filter
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {availableExtras.map((k) => (
                  <DropdownMenuItem key={k} onClick={() => addExtra(k)}>{EXTRA_LABELS[k]}</DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            <FilterField label="Sector">
              <Select value={sector} onValueChange={setSector}>
                <SelectTrigger className={compactTrigger}><SelectValue /></SelectTrigger>
                <SelectContent>{SECTORS.map(s => <SelectItem key={s} value={s}>{s === "all" ? "All sectors" : s}</SelectItem>)}</SelectContent>
              </Select>
            </FilterField>
            <FilterField label="Stage">
              <Select value={stage} onValueChange={setStage}>
                <SelectTrigger className={compactTrigger}><SelectValue /></SelectTrigger>
                <SelectContent>{STAGES.map(s => <SelectItem key={s} value={s}>{s === "all" ? "All stages" : s}</SelectItem>)}</SelectContent>
              </Select>
            </FilterField>
            <FilterField label="Location">
              <Select value={loc} onValueChange={setLoc}>
                <SelectTrigger className={compactTrigger}><SelectValue /></SelectTrigger>
                <SelectContent>{LOCATIONS.map(s => <SelectItem key={s} value={s}>{s === "all" ? "All locations" : s}</SelectItem>)}</SelectContent>
              </Select>
            </FilterField>
            <FilterField label="Founder score (min)">
              <div className="space-y-1 py-1">
                <Slider value={[founderMin]} min={0} max={100} step={5} onValueChange={(v) => setFounderMin(v[0])} />
                <div className="font-mono text-[10px] text-muted-foreground">≥ {founderMin}</div>
              </div>
            </FilterField>

            {visibleExtras.map((k) => (
              <FilterField key={k} label={EXTRA_LABELS[k]} onRemove={() => removeExtra(k)}>
                <ExtraFieldInner k={k} value={extras[k]} onChange={(v) => patchExtra(k, v as never)} allSkills={allSkills} />
              </FilterField>
            ))}
          </div>
          {activeChips.length ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {activeChips.map((c, i) => (
                <button key={i} onClick={c.onRemove} className="inline-flex items-center gap-1 rounded-full border border-border/60 bg-surface-elevated/60 px-2.5 py-0.5 text-xs text-muted-foreground hover:border-brand/40 hover:text-brand">
                  {c.label} <X className="h-3 w-3" />
                </button>
              ))}
            </div>
          ) : null}
        </div>

        {/* Search bar */}
        <div className="rounded-2xl border border-border/60 bg-surface/60 p-4 backdrop-blur">
          <Input
            placeholder='Ask naturally — e.g. "technical founder, Berlin, AI infra, traction"'
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          {activeConstraints.length > 0 ? (
            <>
              <div className="mt-3 flex flex-wrap gap-1.5">
                <span className="mr-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Understood as</span>
                {activeConstraints.map((c) => (
                  <button
                    key={ckey(c)}
                    onClick={() => setDismissedKeys((d) => [...d, ckey(c)])}
                    className="inline-flex items-center gap-1 rounded-full border border-brand/40 bg-brand/10 px-2.5 py-0.5 text-xs text-brand hover:bg-brand/20"
                  >
                    {constraintLabel(c)} <X className="h-3 w-3" />
                  </button>
                ))}
              </div>
              <p className="mt-1.5 text-[11px] text-muted-foreground">Parsed transparently — no black box.</p>
            </>
          ) : null}
          <div className="mt-4 inline-flex rounded-lg border border-border/60 bg-surface-elevated/60 p-1">
            {(["all", "saved", "matched"] as const).map((k) => (
              <button
                key={k}
                onClick={() => setView(k)}
                className={cn("rounded-md px-3 py-1.5 text-sm transition", view === k ? "bg-gradient-brand text-primary-foreground shadow-glow" : "text-muted-foreground hover:text-foreground")}
              >
                {k === "all" ? "All" : k === "saved" ? `Saved (${saved.length})` : "Matched"}
              </button>
            ))}
          </div>
        </div>


        {view === "matched" && !thesisSet ? (
          <div className="rounded-2xl border border-dashed border-border/60 p-10 text-center">
            <p className="text-muted-foreground">Set your thesis to see matched founders.</p>
            <Link to="/thesis" className="mt-3 inline-block rounded-md bg-brand px-4 py-2 text-sm text-primary-foreground">Set your thesis</Link>
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/60 p-10 text-center text-muted-foreground">
            {view === "saved" ? "You haven't saved any founders yet. Save a card to keep it here."
              : view === "matched" ? "No founders match your thesis yet. Try widening your criteria."
              : `No ${tab} founders match your filters.`}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {filtered.map((f) => (
              <FounderCard
                key={f.id}
                f={f}
                saved={saved.includes(f.id)}
                onToggleSave={() => toggleSave(f)}
                invite={inviteByFounder[f.id]}
                onInvite={() => openInvite(f)}
                matchReasons={view === "matched" ? matches[f.id]?.reasons : undefined}
                matchScore={view === "matched" ? matches[f.id]?.score : undefined}
                showDeckBadge={tab === "inbound" && !!f.deck}
              />
            ))}
          </div>
        )}
      </div>

      <Dialog open={!!inviteFor} onOpenChange={(o) => !o && setInviteFor(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite {inviteFor?.name} to apply</DialogTitle>
          </DialogHeader>
          <Textarea rows={8} value={inviteMsg} onChange={(e) => setInviteMsg(e.target.value)} />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setInviteFor(null)}>Cancel</Button>
            <Button className="bg-gradient-brand text-primary-foreground shadow-glow" onClick={sendInvite}>Send</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}

function FilterField({ label, onRemove, children }: { label: string; onRemove?: () => void; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border/60 bg-surface-elevated/40 p-2">
      <div className="mb-1 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground truncate">{label}</span>
        {onRemove ? (
          <button onClick={onRemove} className="text-muted-foreground hover:text-foreground" title="Remove filter">
            <X className="h-3 w-3" />
          </button>
        ) : null}
      </div>
      {children}
    </div>
  );
}

function ExtraFieldInner({ k, value, onChange, allSkills }: {
  k: ExtraKey;
  value: unknown;
  onChange: (v: unknown) => void;
  allSkills: string[];
}) {
  if (k === "completenessMin" || k === "confidenceMin") {
    const v = (value as number | undefined) ?? 0;
    return (
      <div className="space-y-1 py-1">
        <Slider value={[v]} min={0} max={100} step={5} onValueChange={(vv) => onChange(vv[0])} />
        <div className="font-mono text-[10px] text-muted-foreground">≥ {v}{k === "confidenceMin" ? "%" : ""}</div>
      </div>
    );
  }
  if (k === "market") return (
    <Select value={(value as string) ?? ""} onValueChange={onChange}>
      <SelectTrigger className={compactTrigger}><SelectValue placeholder="Any" /></SelectTrigger>
      <SelectContent>{MARKET_OPTIONS.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectContent>
    </Select>
  );
  if (k === "fit") return (
    <Select value={(value as string) ?? ""} onValueChange={onChange}>
      <SelectTrigger className={compactTrigger}><SelectValue placeholder="Any" /></SelectTrigger>
      <SelectContent>{FIT_OPTIONS.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectContent>
    </Select>
  );
  if (k === "source") return (
    <Select value={(value as string) ?? ""} onValueChange={onChange}>
      <SelectTrigger className={compactTrigger}><SelectValue placeholder="Any source" /></SelectTrigger>
      <SelectContent>{SOURCE_OPTIONS.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectContent>
    </Select>
  );
  if (k === "coldStart") return (
    <Select value={(value as string) ?? ""} onValueChange={onChange}>
      <SelectTrigger className={compactTrigger}><SelectValue placeholder="Any" /></SelectTrigger>
      <SelectContent>
        <SelectItem value="only">Only cold-start</SelectItem>
        <SelectItem value="exclude">Exclude cold-start</SelectItem>
      </SelectContent>
    </Select>
  );
  if (k === "contradiction") return (
    <Select value={(value as string) ?? ""} onValueChange={onChange}>
      <SelectTrigger className={compactTrigger}><SelectValue placeholder="Any" /></SelectTrigger>
      <SelectContent>
        <SelectItem value="only">Only flagged</SelectItem>
        <SelectItem value="exclude">Exclude flagged</SelectItem>
      </SelectContent>
    </Select>
  );
  if (k === "skills") {
    const cur = (value as string[] | undefined) ?? [];
    return (
      <div className="flex max-h-24 flex-wrap gap-1 overflow-auto">
        {allSkills.length === 0 ? (
          <span className="text-[10px] text-muted-foreground">No skills in current results.</span>
        ) : allSkills.map((s) => {
          const active = cur.includes(s);
          return (
            <button
              key={s}
              onClick={() => onChange(active ? cur.filter((x) => x !== s) : [...cur, s])}
              className={cn(
                "rounded-full border px-1.5 py-0.5 text-[10px]",
                active ? "border-brand bg-brand/10 text-brand" : "border-border/60 text-muted-foreground hover:border-brand/40",
              )}
            >{s}</button>
          );
        })}
      </div>
    );
  }
  return null;
}
