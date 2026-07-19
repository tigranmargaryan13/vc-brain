import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { FounderCard } from "@/components/founder-card";
import {
  searchFounders, listSaved, saveProject, unsaveProject, listInvitationsForInvestor,
  sendInvitation, getCurrentUser, type FounderProfile, type Invitation, type User,
} from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/hunt")({
  component: HuntPage,
});

const SECTORS = ["all", "AI/ML", "Fintech", "Climate", "Healthtech", "Dev Tools", "Consumer", "Deep Tech", "Biotech", "Cybersecurity", "SaaS"];
const STAGES = ["all", "Pre-seed", "Seed", "Series A"];
const LOCATIONS = ["all", "Berlin", "London", "Paris", "Amsterdam", "Lisbon", "San Francisco", "Tokyo", "Nairobi", "Lagos", "Mexico City"];

const STATE_KEY = "vcbrain.huntState";

function HuntPage() {
  const [user, setUser] = useState<User | null>(null);
  const [q, setQ] = useState("");
  const [sector, setSector] = useState("all");
  const [stage, setStage] = useState("all");
  const [loc, setLoc] = useState("all");
  const [view, setView] = useState<"all" | "saved">("all");
  const [results, setResults] = useState<FounderProfile[]>([]);
  const [saved, setSaved] = useState<string[]>([]);
  const [invites, setInvites] = useState<Invitation[]>([]);
  const [inviteFor, setInviteFor] = useState<FounderProfile | null>(null);
  const [inviteMsg, setInviteMsg] = useState("");

  // restore state
  useEffect(() => {
    getCurrentUser().then(setUser);
    try {
      const raw = sessionStorage.getItem(STATE_KEY);
      if (raw) {
        const s = JSON.parse(raw);
        setQ(s.q ?? ""); setSector(s.sector ?? "all"); setStage(s.stage ?? "all"); setLoc(s.loc ?? "all"); setView(s.view ?? "all");
        setTimeout(() => window.scrollTo(0, s.scroll ?? 0), 50);
      }
    } catch {}
  }, []);
  useEffect(() => {
    sessionStorage.setItem(STATE_KEY, JSON.stringify({ q, sector, stage, loc, view, scroll: window.scrollY }));
  }, [q, sector, stage, loc, view]);

  async function refresh() {
    const [r, s, i] = await Promise.all([
      searchFounders({ q, sector, stage, location: loc, savedOnly: view === "saved" }),
      listSaved(),
      listInvitationsForInvestor(),
    ]);
    setResults(r); setSaved(s); setInvites(i);
  }
  useEffect(() => { void refresh(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [q, sector, stage, loc, view]);

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

  return (
    <AppShell title="Hunt Founders">
      <div className="space-y-6">
        <div className="rounded-2xl border border-border/60 bg-surface/60 p-4 backdrop-blur">
          <div className="grid gap-3 sm:grid-cols-4">
            <Input placeholder="Search founders, projects…" value={q} onChange={(e) => setQ(e.target.value)} className="sm:col-span-2" />
            <Select value={sector} onValueChange={setSector}><SelectTrigger><SelectValue placeholder="Sector" /></SelectTrigger>
              <SelectContent>{SECTORS.map(s => <SelectItem key={s} value={s}>{s === "all" ? "All sectors" : s}</SelectItem>)}</SelectContent>
            </Select>
            <Select value={stage} onValueChange={setStage}><SelectTrigger><SelectValue placeholder="Stage" /></SelectTrigger>
              <SelectContent>{STAGES.map(s => <SelectItem key={s} value={s}>{s === "all" ? "All stages" : s}</SelectItem>)}</SelectContent>
            </Select>
            <Select value={loc} onValueChange={setLoc}><SelectTrigger><SelectValue placeholder="Location" /></SelectTrigger>
              <SelectContent>{LOCATIONS.map(s => <SelectItem key={s} value={s}>{s === "all" ? "All locations" : s}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="mt-4 inline-flex rounded-lg border border-border/60 bg-surface-elevated/60 p-1">
            {(["all", "saved"] as const).map((k) => (
              <button
                key={k}
                onClick={() => setView(k)}
                className={cn("rounded-md px-3 py-1.5 text-sm transition", view === k ? "bg-gradient-brand text-primary-foreground shadow-glow" : "text-muted-foreground hover:text-foreground")}
              >
                {k === "all" ? "All" : `Saved (${saved.length})`}
              </button>
            ))}
          </div>
        </div>

        {results.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/60 p-10 text-center text-muted-foreground">
            {view === "saved" ? "You haven't saved any founders yet. Save a card to keep it here." : "No founders match your filters."}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {results.map((f) => (
              <FounderCard
                key={f.id}
                f={f}
                saved={saved.includes(f.id)}
                onToggleSave={() => toggleSave(f)}
                invite={inviteByFounder[f.id]}
                onInvite={() => openInvite(f)}
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
