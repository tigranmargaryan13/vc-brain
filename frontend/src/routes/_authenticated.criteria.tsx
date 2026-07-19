import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { getCriteria, type CriteriaGroup } from "@/lib/api";

export const Route = createFileRoute("/_authenticated/criteria")({
  component: CriteriaPage,
});

function CriteriaPage() {
  const [groups, setGroups] = useState<CriteriaGroup[]>([]);
  useEffect(() => { getCriteria().then(setGroups); }, []);
  const ranked = [...groups].sort((a, b) => b.weight - a.weight);
  const max = Math.max(...groups.map(g => g.weight), 1);

  return (
    <AppShell title="Fundraising Criteria">
      <div className="space-y-6">
        <div className="rounded-2xl border border-brand/30 bg-gradient-brand/10 p-5 shadow-glow">
          <div className="font-mono text-xs uppercase tracking-widest text-brand">What investors prioritize on VC Brain</div>
          <p className="mt-2 text-sm text-muted-foreground">Use this as a lens: sharpen how you talk about the highest-weighted criteria in your deck and updates.</p>
        </div>
        <div className="rounded-2xl border border-border/60 bg-surface/60 p-6 backdrop-blur">
          <ol className="space-y-5">
            {ranked.map((g, i) => (
              <li key={g.id}>
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-xs text-muted-foreground">#{i + 1}</span>
                  <span className="font-display text-lg font-semibold">{g.label}</span>
                  <span className="ml-auto font-mono text-xs text-brand">weight {g.weight}</span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{g.description}</p>
                <div className="mt-2 h-1.5 rounded-full bg-surface-elevated">
                  <div className="h-full rounded-full bg-gradient-brand" style={{ width: `${(g.weight / max) * 100}%` }} />
                </div>
              </li>
            ))}
          </ol>
        </div>
        <p className="text-xs text-muted-foreground">Criteria are provisional and will evolve.</p>
      </div>
    </AppShell>
  );
}
