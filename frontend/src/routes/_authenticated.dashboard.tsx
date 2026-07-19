import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  getCurrentUser, listInvestments, listFounderStats, searchFounders,
  type User, type Investment, type FounderProfile,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowRight, Compass, Building2 } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend,
  BarChart, Bar, LabelList,
  ScatterChart, Scatter, ZAxis,
} from "recharts";

export const Route = createFileRoute("/_authenticated/dashboard")({
  component: Dashboard,
});

const SERIES_COLORS = ["#2a78d6", "#008300", "#e87ba4", "#eda100"];
const INK = "#1c1e26";
const GRID = "#eaecef";

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

// ------ Seeded RNG for stable mock series ------
function mulberry32(seed: number) {
  return function () {
    let t = (seed += 0x6D2B79F5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function buildRevenueSeries(activeInvestments: Investment[], days: number) {
  const rows: { date: string; label: string; [k: string]: number | string }[] = [];
  const top = activeInvestments.slice(0, 4);
  const rest = activeInvestments.slice(4);
  const companies = [...top.map((i) => i.company), rest.length ? "Other" : null].filter(Boolean) as string[];
  const seeds = companies.map((c) => Array.from(c).reduce((s, ch) => s + ch.charCodeAt(0), 0));
  const now = new Date();
  for (let d = days - 1; d >= 0; d--) {
    const dt = new Date(now);
    dt.setDate(now.getDate() - d);
    const key = dt.toISOString().slice(0, 10);
    const row: { date: string; label: string; [k: string]: number | string } = {
      date: key,
      label: dt.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    };
    companies.forEach((c, idx) => {
      const rand = mulberry32(seeds[idx] + d * 13);
      const base = 1200 + idx * 400;
      const drift = (days - d) * (6 + idx * 2);
      const noise = (rand() - 0.5) * 400;
      row[c] = Math.max(200, Math.round(base + drift + noise));
    });
    rows.push(row);
  }
  return { rows, companies };
}

function InvestorDashboard() {
  const navigate = useNavigate();
  const [inv, setInv] = useState<Investment[] | null>(null);
  const [founders, setFounders] = useState<FounderProfile[] | null>(null);
  const [range, setRange] = useState<7 | 30 | 90>(30);

  useEffect(() => {
    listInvestments().then(setInv);
    searchFounders({}).then(setFounders);
  }, []);

  const active = useMemo(() => (inv ?? []).filter((i) => i.status === "Active"), [inv]);
  const revenue = useMemo(() => buildRevenueSeries(active, range), [active, range]);
  const bySector = useMemo(() => {
    const m = new Map<string, number>();
    for (const i of inv ?? []) m.set(i.sector, (m.get(i.sector) ?? 0) + i.amount);
    return Array.from(m.entries()).map(([sector, amount]) => ({ sector, amount, label: `$${(amount / 1000).toFixed(0)}k` }))
      .sort((a, b) => b.amount - a.amount);
  }, [inv]);
  const scatterData = useMemo(() => {
    return (founders ?? [])
      .filter((f) => typeof f.completeness === "number")
      .map((f) => ({
        id: f.id,
        x: f.completeness ?? 0,
        y: f.scores.founder,
        z: 100,
        name: f.name,
        project: f.projects[0]?.name ?? "",
        sector: f.projects[0]?.sector ?? "",
      }));
  }, [founders]);

  if (!inv) return null;
  const total = active.reduce((s, i) => s + i.amount, 0);
  const sectors = new Set(inv.map((i) => i.sector));

  if (inv.length === 0) {
    return (
      <div className="rounded-2xl border border-brand/40 bg-brand/5 p-8 text-center shadow-glow">
        <h2 className="font-display text-2xl font-semibold">Welcome. Let's set you up.</h2>
        <p className="mt-2 text-muted-foreground">Two steps to your first ranked pipeline.</p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Button asChild className="bg-brand text-primary-foreground hover:opacity-90">
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
        <StatCard label="Active deals" value={String(active.length)} />
        <StatCard label="Sectors covered" value={String(sectors.size)} />
      </div>

      {/* Portfolio revenue */}
      <div className="rounded-2xl border border-border bg-surface p-5 shadow-glow">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="font-display text-sm font-semibold">Portfolio revenue (daily)</div>
            <div className="mt-0.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Last {range} days · mock</div>
          </div>
          <div className="inline-flex overflow-hidden rounded-lg border border-border">
            {([7, 30, 90] as const).map((r) => (
              <button key={r} onClick={() => setRange(r)}
                className={`px-3 py-1 text-xs ${range === r ? "bg-brand text-primary-foreground" : "bg-surface text-muted-foreground hover:text-foreground"}`}>
                {r}d
              </button>
            ))}
          </div>
        </div>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={revenue.rows} margin={{ top: 8, right: 60, left: 8, bottom: 8 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="label" stroke={INK} fontSize={11} tickLine={false} axisLine={{ stroke: GRID }} />
              <YAxis stroke={INK} fontSize={11} tickLine={false} axisLine={{ stroke: GRID }} tickFormatter={(v) => `$${Math.round(v / 100) / 10}k`} />
              <Tooltip
                contentStyle={{ background: "white", border: `1px solid ${GRID}`, borderRadius: 8, color: INK, fontSize: 12 }}
                labelStyle={{ color: INK }}
              />
              <Legend wrapperStyle={{ fontSize: 11, color: INK }} />
              {revenue.companies.map((c, idx) => (
                <Line
                  key={c}
                  type="monotone"
                  dataKey={c}
                  stroke={SERIES_COLORS[idx % SERIES_COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                >
                  <LabelList
                    dataKey={c}
                    position="right"
                    content={(props) => {
                      const { x, y, index, value } = props as { x?: number; y?: number; index?: number; value?: number };
                      if (index !== revenue.rows.length - 1 || x == null || y == null) return null;
                      return (
                        <text x={(x as number) + 6} y={y as number} fill={INK} fontSize={10} dy={3}>
                          {c} · ${Math.round(((value as number) ?? 0) / 100) / 10}k
                        </text>
                      );
                    }}
                  />
                </Line>
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Founder landscape + Sector bars */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-border bg-surface p-5 shadow-glow">
          <div className="mb-3 font-display text-sm font-semibold">Founder landscape</div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 12, right: 12, left: 0, bottom: 8 }}>
                <CartesianGrid stroke={GRID} />
                <XAxis type="number" dataKey="x" name="Completeness" domain={[0, 100]} unit="%" stroke={INK} fontSize={11} axisLine={{ stroke: GRID }} tickLine={false} />
                <YAxis type="number" dataKey="y" name="Founder score" domain={[0, 100]} stroke={INK} fontSize={11} axisLine={{ stroke: GRID }} tickLine={false} />
                <ZAxis type="number" dataKey="z" range={[80, 80]} />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3", stroke: GRID }}
                  contentStyle={{ background: "white", border: `1px solid ${GRID}`, borderRadius: 8, color: INK, fontSize: 12 }}
                  formatter={(_, __, entry) => {
                    const p = entry?.payload as { name: string; project: string; sector: string; x: number; y: number } | undefined;
                    if (!p) return "";
                    return [`${p.name} — ${p.project} · ${p.sector}`, `Score ${p.y} · ${p.x}% data`];
                  }}
                />
                <Scatter
                  data={scatterData}
                  fill={SERIES_COLORS[0]}
                  onClick={(pt) => {
                    const p = pt as unknown as { id?: string };
                    if (p?.id) navigate({ to: "/founder/$id", params: { id: p.id } });
                  }}
                  style={{ cursor: "pointer" }}
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-surface p-5 shadow-glow">
          <div className="mb-3 font-display text-sm font-semibold">Portfolio by sector</div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={bySector} layout="vertical" margin={{ top: 8, right: 60, left: 8, bottom: 8 }}>
                <CartesianGrid stroke={GRID} horizontal={false} />
                <XAxis type="number" stroke={INK} fontSize={11} axisLine={{ stroke: GRID }} tickLine={false} tickFormatter={(v) => `$${Math.round(v / 1000)}k`} />
                <YAxis type="category" dataKey="sector" stroke={INK} fontSize={11} axisLine={{ stroke: GRID }} tickLine={false} width={90} />
                <Tooltip
                  contentStyle={{ background: "white", border: `1px solid ${GRID}`, borderRadius: 8, color: INK, fontSize: 12 }}
                  formatter={((v: number) => `$${v.toLocaleString()}`) as any}
                />
                <Bar dataKey="amount" fill={SERIES_COLORS[0]} radius={[4, 4, 4, 4]}>
                  <LabelList dataKey="label" position="right" fill={INK} fontSize={11} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Portfolio table */}
      <div className="rounded-2xl border border-border bg-surface">
        <div className="border-b border-border px-5 py-4 font-display text-sm font-semibold">Portfolio</div>
        <div className="divide-y divide-border">
          {inv.map((i) => (
            <div key={i.id} className="grid grid-cols-2 items-center gap-3 px-5 py-3 sm:grid-cols-6">
              <div className="col-span-2 font-medium">{i.company}</div>
              <div className="text-sm text-muted-foreground">{i.sector}</div>
              <div className="text-sm text-muted-foreground">{i.stage}</div>
              <div className="font-mono text-sm">${(i.amount / 1000).toFixed(0)}k</div>
              <div className="text-right">
                <Badge variant={i.status === "Active" ? "default" : "outline"} className={i.status === "Active" ? "bg-brand text-primary-foreground" : ""}>
                  {i.status}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      </div>
      <Button asChild variant="outline"><Link to="/hunt">Find your next investment <Compass className="ml-1.5 h-4 w-4" /></Link></Button>
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
      <div className="rounded-2xl border border-border bg-surface p-5 shadow-glow">
        <div className="mb-3 font-display text-sm font-semibold">Per-project reach</div>
        {stats.byProject.length === 0 ? (
          <div className="text-sm text-muted-foreground">No companies yet. <Link to="/companies" className="text-brand hover:underline">Add a start-up</Link> to start collecting signals.</div>
        ) : (
          <div className="space-y-3">
            {stats.byProject.map((p) => {
              const max = Math.max(...stats.byProject.map((x) => x.views), 1);
              return (
                <div key={p.name}>
                  <div className="mb-1 flex justify-between text-sm"><span>{p.name}</span><span className="font-mono text-muted-foreground">{p.views} views · {p.saves} saves</span></div>
                  <div className="h-1.5 rounded-full bg-muted"><div className="h-full rounded-full bg-brand" style={{ width: `${(p.views / max) * 100}%` }} /></div>
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
    <div className="rounded-2xl border border-border bg-surface p-5">
      <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="mt-1 font-display text-2xl font-semibold">{value}</div>
    </div>
  );
}
