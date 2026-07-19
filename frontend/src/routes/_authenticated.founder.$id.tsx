import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  getFounder, generateMemo, listInvitationsForInvestor, sendInvitation, getCurrentUser,
  type FounderProfile, type Memo, type Invitation, type User,
} from "@/lib/api";
import { ScoreTriad, ColdStartBadge, ContradictionBadge, ClaimLine } from "@/components/scores";
import { MemoView } from "@/components/memo";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { ArrowLeft, Sparkles } from "lucide-react";

export const Route = createFileRoute("/_authenticated/founder/$id")({
  component: FounderDetail,
});

function FounderDetail() {
  const { id } = Route.useParams();
  const [f, setF] = useState<FounderProfile | null | undefined>(undefined);
  const [memo, setMemo] = useState<Memo | null>(null);
  const [loadingMemo, setLoadingMemo] = useState(false);
  const [invite, setInvite] = useState<Invitation | undefined>();
  const [user, setUser] = useState<User | null>(null);
  const [openInvite, setOpenInvite] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    getCurrentUser().then(setUser);
    getFounder(id).then(setF);
    listInvitationsForInvestor().then((all) => setInvite(all.find((i) => i.founderId === id)));
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
    } catch (e) { toast.error(e instanceof Error ? e.message : "Failed"); }
  }

  return (
    <AppShell title={f.name}>
      <div className="space-y-6">
        <div>
          <Link to="/hunt" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-brand"><ArrowLeft className="h-3.5 w-3.5" /> Back to Hunt</Link>
        </div>
        <header className="rounded-2xl border border-border/60 bg-surface/60 p-6 backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="font-display text-2xl font-semibold">{f.name}</h2>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <span>{f.location}</span>
                {f.projects.map((pr) => (
                  <Badge key={pr.id} variant="outline" className="border-border/60 text-[10px] uppercase tracking-widest">{pr.name} · {pr.sector} · {pr.stage}</Badge>
                ))}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {f.coldStart ? <ColdStartBadge /> : null}
              {f.hasContradiction ? <ContradictionBadge /> : null}
            </div>
          </div>
          <div className="mt-6"><ScoreTriad scores={f.scores} /></div>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button className="bg-gradient-brand text-primary-foreground shadow-glow" disabled={loadingMemo} onClick={onGenerate}>
              <Sparkles className="mr-1.5 h-4 w-4" /> {loadingMemo ? "Generating…" : memo ? "Regenerate memo" : "Generate memo"}
            </Button>
            {invite && invite.status !== "sent" ? (
              <Badge variant="outline" className={invite.status === "accepted" ? "border-emerald-500/40 text-emerald-300" : "border-rose-500/40 text-rose-300"}>
                Invitation {invite.status}
              </Badge>
            ) : invite ? (
              <Badge variant="outline" className="border-brand/40 text-brand">Invited</Badge>
            ) : (
              <Button variant="outline" onClick={openInviteDialog}>Invite to apply</Button>
            )}
          </div>
        </header>

        <section className="rounded-2xl border border-border/60 bg-surface/60 p-6 backdrop-blur">
          <h3 className="mb-4 font-display text-lg font-semibold">Evidence</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {f.evidence.map((e, i) => <ClaimLine key={i} claim={e} unknown={e.unknown} />)}
          </div>
        </section>

        {memo ? (
          <section>
            <h3 className="mb-4 font-display text-lg font-semibold">Investment memo — {p.name}</h3>
            <MemoView memo={memo} />
          </section>
        ) : null}
      </div>

      <Dialog open={openInvite} onOpenChange={setOpenInvite}>
        <DialogContent>
          <DialogHeader><DialogTitle>Invite {f.name}</DialogTitle></DialogHeader>
          <Textarea rows={8} value={msg} onChange={(e) => setMsg(e.target.value)} />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpenInvite(false)}>Cancel</Button>
            <Button className="bg-gradient-brand text-primary-foreground shadow-glow" onClick={send}>Send</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
