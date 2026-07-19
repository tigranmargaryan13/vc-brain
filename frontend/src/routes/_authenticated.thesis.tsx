import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { getThesis, saveThesis, getCriteria, type Thesis, type CriteriaGroup } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

export const Route = createFileRoute("/_authenticated/thesis")({
  component: ThesisPage,
});

const SECTORS = ["AI/ML", "Fintech", "Climate", "Healthtech", "Dev Tools", "Consumer", "Deep Tech", "Biotech", "Cybersecurity", "SaaS"];
const STAGES = ["Pre-seed", "Seed", "Series A"];
const RISK = ["Conservative", "Balanced", "Aggressive"];

function ThesisPage() {
  const [t, setT] = useState<Thesis | null>(null);
  const [groups, setGroups] = useState<CriteriaGroup[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => { getThesis().then(setT); getCriteria().then(setGroups); }, []);
  if (!t) return <AppShell title="Thesis"><div className="text-muted-foreground">Loading…</div></AppShell>;

  function toggleSector(s: string) {
    setT((prev) => prev ? { ...prev, sectors: prev.sectors.includes(s) ? prev.sectors.filter(x => x !== s) : [...prev.sectors, s] } : prev);
  }

  async function onSave() {
    setSaving(true);
    try { const saved = await saveThesis(t!); setT(saved); toast.success("Thesis saved. Matches and notifications will re-rank."); }
    finally { setSaving(false); }
  }

  return (
    <AppShell title="Thesis">
      <div className="space-y-6">
        <div className="rounded-2xl border border-border/60 bg-surface/60 p-6 backdrop-blur space-y-5">
          <div>
            <Label className="font-mono text-[10px] uppercase tracking-widest text-brand">Sectors</Label>
            <div className="mt-2 flex flex-wrap gap-2">
              {SECTORS.map(s => (
                <button key={s} onClick={() => toggleSector(s)}
                  className={cn("rounded-full border px-3 py-1 text-sm transition",
                    t.sectors.includes(s)
                      ? "border-brand bg-gradient-brand/20 text-foreground shadow-glow"
                      : "border-border/60 bg-surface-elevated/40 text-muted-foreground hover:border-brand/40")}>
                  {s}
                </button>
              ))}
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Stage</Label>
              <Select value={t.stage} onValueChange={(v) => setT({ ...t, stage: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{STAGES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Risk appetite</Label>
              <Select value={t.riskAppetite} onValueChange={(v) => setT({ ...t, riskAppetite: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{RISK.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-2"><Label>Geography</Label><Input value={t.geography} onChange={(e) => setT({ ...t, geography: e.target.value })} placeholder="Europe, US, LATAM…" /></div>
            <div className="space-y-2"><Label>Check size</Label><Input value={t.checkSize} onChange={(e) => setT({ ...t, checkSize: e.target.value })} placeholder="$250k–$1M" /></div>
            <div className="space-y-2 sm:col-span-2"><Label>Ownership target</Label><Input value={t.ownershipTarget} onChange={(e) => setT({ ...t, ownershipTarget: e.target.value })} placeholder="5–10%" /></div>
          </div>
        </div>

        <div className="rounded-2xl border border-border/60 bg-surface/60 p-6 backdrop-blur">
          <div className="mb-4">
            <h3 className="font-display text-lg font-semibold">Criteria weights</h3>
            <p className="text-xs text-muted-foreground">Tune how heavily each dimension counts when we rank matches. Criteria are provisional and will evolve.</p>
          </div>
          <div className="space-y-5">
            {groups.map((g) => (
              <div key={g.id}>
                <div className="mb-1 flex justify-between text-sm">
                  <span><span className="font-medium">{g.label}</span> <span className="text-muted-foreground">— {g.description}</span></span>
                  <span className="font-mono text-xs text-brand">{t.weights[g.id] ?? 50}</span>
                </div>
                <Slider min={0} max={100} step={5} value={[t.weights[g.id] ?? 50]} onValueChange={([v]) => setT({ ...t, weights: { ...t.weights, [g.id]: v } })} />
              </div>
            ))}
          </div>
        </div>

        <Button className="bg-gradient-brand text-primary-foreground shadow-glow" disabled={saving} onClick={onSave}>{saving ? "Saving…" : "Save thesis"}</Button>
      </div>
    </AppShell>
  );
}
