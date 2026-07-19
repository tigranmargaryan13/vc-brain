import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  getFounder, generateMemo, listInvitationsForInvestor, sendInvitation, getCurrentUser,
  countInvitationsForFounder,
  type FounderProfile, type Memo, type Invitation, type User,
} from "@/lib/api";
import { ScoreTriad, ColdStartBadge, ContradictionBadge, ClaimLine, ScoreDimensionsBreakdown } from "@/components/scores";
import { MemoView } from "@/components/memo";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import {
  Collapsible, CollapsibleContent, CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { toast } from "sonner";
import {
  ArrowLeft, Sparkles, Github, Linkedin, Globe, ExternalLink,
  TrendingUp, MessageSquare, ThumbsUp, Calendar, Clock, Mail, ChevronDown,
} from "lucide-react";

export const Route = createFileRoute("/_authenticated/founder/$id")({
  component: FounderDetail,
});

const CARD = "rounded-2xl border border-border bg-surface p-6 shadow-glow";

function FounderDetail() {
  const { id } = Route.useParams();
  const [f, setF] = useState<FounderProfile | null | undefined>(undefined);
  const [memo, setMemo] = useState<Memo | null>(null);
  const [loadingMemo, setLoadingMemo] = useState(false);
  const [invite, setInvite] = useState<Invitation | undefined>();
  const [inviteCount, setInviteCount] = useState<number>(0);
  const [user, setUser] = useState<User | null>(null);
  const [openInvite, setOpenInvite] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    getCurrentUser().then(setUser);
    getFounder(id).then(setF);
    listInvitationsForInvestor().then((all) => setInvite(all.find((i) => i.founderId === id)));
    countInvitationsForFounder(id).then(setInviteCount);
  }, [id]);

  if (f === undefined) return <AppShell title="Founder"><div className="text-muted-foreground">Loading…</div></AppShell>;
  if (!f) return <AppShell title="Founder"><div className="text-muted-foreground">Not found. <Link to="/hunt" className="text-brand">Back to Hunt</Link></div></AppShell>;

  const p = f.projects[0];

  async function onGenerate() {
    setLoadingMemo(true);
    try {
      const m = await generateMemo(f!.id, p.id);
      setMemo(m);
      toast.success("Memo ready.");
    } finally { setLoadingMemo(false); }
  }

  function openInviteDialog() {
    setMsg(`Hi ${f!.name.split(" ")[0]},\n\n${p.name} caught our eye — the way you frame ${p.sector} at ${p.stage} lines up with what we're actively backing. Would you be open to a 20-min intro call?\n\n— ${user?.displayName ?? user?.email ?? "the team"}`);
    setOpenInvite(true);
  }
  async function send() {
    try {
      await sendInvitation({ founderId: f!.id, founderEmail: f!.email, projectId: p.id, message: msg });
      toast.success("Invitation sent.");
      setOpenInvite(false);
      const all = await listInvitationsForInvestor();
      setInvite(all.find((i) => i.founderId === f!.id));
      setInviteCount(await countInvitationsForFounder(f!.id));
    } catch (e) { toast.error(e instanceof Error ? e.message : "Failed"); }
  }

  return (
    <AppShell title={f.name}>
      <div className="space-y-6">
        <div>
          <Link to="/hunt" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-brand"><ArrowLeft className="h-3.5 w-3.5" /> Back to Hunt</Link>
        </div>

        <FounderCardSection f={f} invitedByCount={inviteCount} />
        <ScoresCard f={f} />

        <section className={CARD}>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-display text-lg font-semibold">Investment memo — {p.name}</h3>
            <div className="flex flex-wrap gap-3">
              <Button className="bg-brand text-primary-foreground hover:opacity-90" disabled={loadingMemo} onClick={onGenerate}>
                <Sparkles className="mr-1.5 h-4 w-4" /> {loadingMemo ? "Generating…" : memo ? "Regenerate memo" : "Generate memo"}
              </Button>
              {invite && invite.status !== "sent" ? (
                <Badge variant="outline" className={invite.status === "accepted" ? "border-emerald-600/40 text-emerald-700" : "border-rose-600/40 text-rose-700"}>
                  Invitation {invite.status}
                </Badge>
              ) : invite ? (
                <Badge variant="outline" className="border-brand/40 text-brand">Invited</Badge>
              ) : (
                <Button variant="outline" onClick={openInviteDialog}>Invite to apply</Button>
              )}
            </div>
          </div>
          {memo ? <MemoView memo={memo} /> : <p className="text-sm text-muted-foreground">No memo yet — generate one to see the full evidence-backed write-up.</p>}
        </section>

        <ProjectCard f={f} />

        <section className={CARD}>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-display text-lg font-semibold">Insights</h3>
            <div className="flex flex-wrap items-center gap-2">
              {f.coldStart ? <ColdStartBadge /> : null}
              {f.hasContradiction ? <ContradictionBadge /> : null}
            </div>
          </div>
          <InsightsList evidence={f.evidence} />
        </section>
      </div>

      <Dialog open={openInvite} onOpenChange={setOpenInvite}>
        <DialogContent>
          <DialogHeader><DialogTitle>Invite {f.name}</DialogTitle></DialogHeader>
          <Textarea rows={8} value={msg} onChange={(e) => setMsg(e.target.value)} />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpenInvite(false)}>Cancel</Button>
            <Button className="bg-brand text-primary-foreground hover:opacity-90" onClick={send}>Send</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}

function ProjectCard({ f }: { f: FounderProfile }) {
  const p = f.projects[0];
  const d = f.details;
  const stats: { icon: typeof ThumbsUp; label: string; value: string }[] = [];
  if (d) {
    if (typeof d.upvotes === "number") stats.push({ icon: ThumbsUp, label: "Upvotes", value: d.upvotes.toLocaleString() });
    if (typeof d.comments === "number") stats.push({ icon: MessageSquare, label: "Comments", value: d.comments.toLocaleString() });
    if (typeof d.hnPoints === "number") stats.push({ icon: TrendingUp, label: "HN points", value: d.hnPoints.toLocaleString() });
    if (d.launched) stats.push({ icon: Calendar, label: "Launched", value: d.launched });
    if (typeof d.domainAgeDays === "number") stats.push({ icon: Clock, label: "Domain age", value: `${d.domainAgeDays}d` });
  }
  return (
    <section className={CARD}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-3xl font-semibold tracking-tight">{p.name}</h2>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge variant="outline" className="border-border">{p.sector}</Badge>
            <Badge variant="outline" className="border-border">{p.stage}</Badge>
            {d?.industry?.split(";").map((t) => t.trim()).filter(Boolean).map((t) => (
              <span key={t} className="rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] uppercase tracking-widest text-muted-foreground">{t}</span>
            ))}
          </div>
        </div>
        {typeof f.completeness === "number" ? (
          <div className="w-40 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Completeness</span>
              <span className="font-mono text-xs">{f.completeness}%</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-muted">
              <div className="h-full rounded-full bg-brand" style={{ width: `${Math.max(4, Math.min(100, f.completeness))}%` }} />
            </div>
          </div>
        ) : null}
      </div>
      <p className="mt-4 text-sm leading-relaxed text-foreground">
        {p.description ?? p.oneLiner}
      </p>
      {stats.length || d?.freshDomain ? (
        <div className="mt-5 flex flex-wrap gap-2">
          {stats.map((s) => (
            <div key={s.label} className="inline-flex items-center gap-2 rounded-lg border border-border bg-muted/60 px-3 py-1.5">
              <s.icon className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{s.label}</span>
              <span className="font-mono text-xs text-foreground">{s.value}</span>
            </div>
          ))}
          {d?.freshDomain ? (
            <span className="inline-flex items-center gap-1 rounded-lg border border-amber-600/40 bg-amber-50 px-3 py-1.5 text-xs text-amber-800">
              Fresh domain
            </span>
          ) : null}
        </div>
      ) : null}
      {(d?.links?.length || f.contact?.website) ? (
        <div className="mt-5 flex flex-wrap gap-2">
          {d?.links?.map((l) => {
            const lbl = l.label.toLowerCase();
            const Icon = lbl.includes("github") ? Github : lbl.includes("linkedin") ? Linkedin : lbl.includes("web") || lbl.includes("site") ? Globe : ExternalLink;
            return (
              <a key={l.url} href={l.url} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-3 py-1 text-xs text-muted-foreground hover:border-brand/40 hover:text-brand">
                <Icon className="h-3 w-3" />
                {l.label}
              </a>
            );
          })}
          {f.contact?.website && !d?.links?.some((l) => l.url === f.contact!.website) ? (
            <a href={f.contact.website} target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-3 py-1 text-xs text-muted-foreground hover:border-brand/40 hover:text-brand">
              <Globe className="h-3 w-3" />
              Website
            </a>
          ) : null}
        </div>
      ) : null}
      <DeckSection f={f} />
    </section>
  );
}

function DeckSection({ f }: { f: FounderProfile }) {
  const deck = f.deck;
  if (!deck || (!deck.embedUrl && !deck.pdfUrl)) {
    return (
      <div className="mt-5 border-t border-border pt-4">
        <div className="mb-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Pitch deck</div>
        <p className="text-sm text-muted-foreground">No deck submitted — invite them to apply.</p>
      </div>
    );
  }
  return (
    <div className="mt-5 border-t border-border pt-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Pitch deck</div>
        <div className="flex flex-wrap gap-2">
          {deck.embedUrl ? (
            <a href={deck.embedUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-full border border-brand/40 bg-brand/5 px-3 py-1 text-xs text-brand hover:opacity-90">
              <ExternalLink className="h-3 w-3" /> Open deck
            </a>
          ) : null}
          {deck.pdfUrl ? (
            <a href={deck.pdfUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-3 py-1 text-xs text-muted-foreground hover:text-brand hover:border-brand/40">
              <ExternalLink className="h-3 w-3" /> Open PDF
            </a>
          ) : null}
        </div>
      </div>
      {deck.embedUrl ? (
        <div className="relative overflow-hidden rounded-lg border border-border bg-muted" style={{ paddingBottom: "56.25%" }}>
          <iframe
            src={deck.embedUrl}
            loading="lazy"
            title={`${f.projects[0].name} pitch deck`}
            allow="fullscreen"
            className="absolute inset-0 h-full w-full"
          />
        </div>
      ) : null}
      {deck.notes ? <p className="mt-2 text-xs text-muted-foreground">{deck.notes}</p> : null}
    </div>
  );
}

function FounderCardSection({ f, invitedByCount }: { f: FounderProfile; invitedByCount: number }) {
  const c = f.contact;
  return (
    <section className={CARD}>
      <div className="flex flex-wrap items-start gap-4">
        <div className="grid h-14 w-14 shrink-0 place-items-center rounded-full border border-border bg-brand/5 font-display text-lg font-semibold text-foreground">
          {f.name.split(" ").map((n) => n[0]).filter(Boolean).slice(0, 2).join("").toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-display text-xl font-semibold">{f.name}</h3>
            {f.details?.source ? (
              <Badge variant="outline" className="border-brand/40 text-[10px] uppercase tracking-widest text-brand">{f.details.source}</Badge>
            ) : null}
          </div>
          <div className="mt-1 text-sm text-muted-foreground">{f.location}</div>
          {f.bio ? <p className="mt-3 text-sm leading-relaxed text-foreground">{f.bio}</p> : null}
          {f.skills?.length ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {f.skills.map((s) => (
                <span key={s} className="rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] uppercase tracking-widest text-muted-foreground">{s}</span>
              ))}
            </div>
          ) : null}
          {(c?.email || c?.linkedin || c?.website) ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {c.email ? (
                <a href={`mailto:${c.email}`} className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-3 py-1 text-xs text-muted-foreground hover:text-brand hover:border-brand/40">
                  <Mail className="h-3 w-3" /> {c.email}
                </a>
              ) : null}
              {c.linkedin ? (
                <a href={c.linkedin} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-3 py-1 text-xs text-muted-foreground hover:text-brand hover:border-brand/40">
                  <Linkedin className="h-3 w-3" /> LinkedIn
                </a>
              ) : null}
              {c.website ? (
                <a href={c.website} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-3 py-1 text-xs text-muted-foreground hover:text-brand hover:border-brand/40">
                  <Globe className="h-3 w-3" /> Website
                </a>
              ) : null}
            </div>
          ) : null}
          <div className="mt-4 inline-flex items-center gap-1.5 rounded-full border border-brand/30 bg-brand/5 px-3 py-1 text-xs text-brand">
            Invited by {invitedByCount} investor{invitedByCount === 1 ? "" : "s"}
          </div>
        </div>
      </div>
    </section>
  );
}

function ScoresCard({ f }: { f: FounderProfile }) {
  return (
    <section className={CARD}>
      <h3 className="mb-4 font-display text-lg font-semibold">Scores</h3>
      <ScoreTriad scores={f.scores} />
      {f.dimensions?.length ? (
        <div className="mt-6 border-t border-border pt-5">
          <div className="mb-3 font-mono text-[11px] uppercase tracking-widest text-muted-foreground">Score dimensions</div>
          <ScoreDimensionsBreakdown dimensions={f.dimensions} />
        </div>
      ) : null}
    </section>
  );
}

function InsightsList({ evidence }: { evidence: FounderProfile["evidence"] }) {
  const grouped = useMemo(() => {
    if (evidence.length <= 6) return null;
    const map = new Map<string, typeof evidence>();
    for (const e of evidence) {
      const key = e.sourceLabel || "Other";
      const arr = map.get(key) ?? [];
      arr.push(e);
      map.set(key, arr);
    }
    return Array.from(map.entries());
  }, [evidence]);

  if (!grouped) {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        {evidence.map((e, i) => <ClaimLine key={i} claim={e} unknown={e.unknown} />)}
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {grouped.map(([label, items]) => (
        <Collapsible key={label} defaultOpen>
          <CollapsibleTrigger className="flex w-full items-center justify-between rounded-lg border border-border bg-muted/40 px-4 py-2 text-left text-sm hover:bg-muted">
            <span className="font-medium">{label}</span>
            <span className="flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
              {items.length}
              <ChevronDown className="h-3.5 w-3.5" />
            </span>
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-3">
            <div className="grid gap-3 sm:grid-cols-2">
              {items.map((e, i) => <ClaimLine key={i} claim={e} unknown={e.unknown} />)}
            </div>
          </CollapsibleContent>
        </Collapsible>
      ))}
    </div>
  );
}
