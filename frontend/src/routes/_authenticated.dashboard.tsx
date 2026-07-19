import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  getCurrentUser, listInvestments, listFounderStats, type User, type Investment,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowRight, Compass, Building2 } from "lucide-react";

export const Route = createFileRoute("/_authenticated/dashboard")({
  component: Dashboard,
});

function Dashboard() {
  const [user, setUser] = useState<User | null>(null);
  useEffect(() => { getCurrentUser().then((u) => setUser(u)); }, []);
  if (!user) return null;
  return (
    <AppShell title="Dashboard">
      {user.persona === "investor" ? <InvestorDashboard /> : <FounderDashboard />}
    </AppShell>
  );
}

function InvestorDashboard() {
  const navigate = useNavigate();
  const [inv, setInv] = useState<Investment[] | null>(null);
  useEffect(() => { listInvestments().then(setInv); }, []);
  if (!inv) return null;
  const total = inv.filter(i => i.status === "Active").reduce((s, i) => s + i.amount, 0);
  const sectors = new Set(inv.map(i => i.sector));
  if (inv.length === 0) {
    return (
      <div className="rounded-2xl border border-brand/40 bg-gradient-brand/10 p-8 text-center shadow-glow">
        <h2 className="font-display text-2xl font-semibold">Welcome. Let's set you up.</h2>
        <p className="mt-2 text-muted-foreground">Two steps to your first ranked pipeline.</p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Button asChild className="bg-gradient-brand text-primary-foreground shadow-glow">
            <Link to="/thesis">1. Set your thesis <ArrowRight className="ml-1 h-4 w-4" /></Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/hunt">2. Hunt founders <Compass className="ml-1 h-4 w-4" /></Link>
          </Button>
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Total invested" value={`$${(total / 1_000_000).toFixed(2)}M`} />
        <StatCard label="Active deals" value={String(inv.filter(i => i.status === "Active").length)} />
        <StatCard label="Sectors covered" value={String(sectors.size)} />
      </div>
      <div className="rounded-2xl border border-border/60 bg-surface/60 backdrop-blur">
        <div className="border-b border-border/60 px-5 py-4 font-display text-sm font-semibold">Portfolio</div>
        <div className="divide-y divide-border/40">
          {inv.map((i) => (
            <div key={i.id} className="grid grid-cols-2 items-center gap-3 px-5 py-3 sm:grid-cols-6">
              <div className="col-span-2 font-medium">{i.company}</div>
              <div className="text-sm text-muted-foreground">{i.sector}</div>
              <div className="text-sm text-muted-foreground">{i.stage}</div>
              <div className="font-mono text-sm">${(i.amount / 1000).toFixed(0)}k</div>
              <div className="text-right">
                <Badge variant={i.status === "Active" ? "default" : "outline"} className={i.status === "Active" ? "bg-gradient-brand text-primary-foreground" : ""}>
                  {i.status}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      </div>
      <Button asChild variant="outline"><Link to="/hunt">Find your next investment <Compass className="ml-1.5 h-4 w-4" /></Link></Button>
      {void navigate}
    </div>
  );
}

function FounderDashboard() {
  const [stats, setStats] = useState<Awaited<ReturnType<typeof listFounderStats>> | null>(null);
  useEffect(() => { listFounderStats().then(setStats); }, []);
  if (!stats) return null;
  const funnel = [
    { label: "Profile views", v: stats.profileViews },
    { label: "Shortlisted", v: stats.shortlisted },
    { label: "Invitations", v: stats.invitations },
    { label: "Accepted", v: stats.accepted },
  ];
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-4">
        {funnel.map((f) => <StatCard key={f.label} label={f.label} value={String(f.v)} />)}
      </div>
      <div className="rounded-2xl border border-border/60 bg-surface/60 p-5 backdrop-blur">
        <div className="mb-3 font-display text-sm font-semibold">Per-project reach</div>
        {stats.byProject.length === 0 ? (
          <div className="text-sm text-muted-foreground">No companies yet. <Link to="/companies" className="text-brand hover:underline">Add a start-up</Link> to start collecting signals.</div>
        ) : (
          <div className="space-y-3">
            {stats.byProject.map((p) => {
              const max = Math.max(...stats.byProject.map(x => x.views), 1);
              return (
                <div key={p.name}>
                  <div className="mb-1 flex justify-between text-sm"><span>{p.name}</span><span className="font-mono text-muted-foreground">{p.views} views · {p.saves} saves</span></div>
                  <div className="h-1.5 rounded-full bg-surface-elevated"><div className="h-full rounded-full bg-gradient-brand" style={{ width: `${(p.views / max) * 100}%` }} /></div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      <Button asChild variant="outline"><Link to="/companies">Manage companies <Building2 className="ml-1.5 h-4 w-4" /></Link></Button>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-surface/60 p-5 backdrop-blur">
      <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="mt-1 font-display text-2xl font-semibold">{value}</div>
    </div>
  );
}
