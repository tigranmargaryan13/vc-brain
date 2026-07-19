import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  getCurrentUser, listCompanies, listFounderStats,
  type User, type Company,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Building2, Mail, Globe, Info } from "lucide-react";

export const Route = createFileRoute("/_authenticated/profile")({
  component: MyProfile,
});

const CARD = "rounded-2xl border border-border bg-surface p-6 shadow-glow";

function MyProfile() {
  const [user, setUser] = useState<User | null>(null);
  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [stats, setStats] = useState<Awaited<ReturnType<typeof listFounderStats>> | null>(null);

  useEffect(() => {
    getCurrentUser().then(setUser);
    listCompanies().then(setCompanies);
    listFounderStats().then(setStats);
  }, []);

  if (!user || !companies || !stats) return <AppShell title="My Profile"><div className="text-muted-foreground">Loading…</div></AppShell>;

  const initials = (user.displayName ?? user.email).split(/[\s@.]+/).map((w) => w[0]).filter(Boolean).slice(0, 2).join("").toUpperCase();

  return (
    <AppShell title="My Profile">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-brand/30 bg-brand/5 p-4">
          <div className="flex items-center gap-2 text-sm text-brand">
            <Info className="h-4 w-4" /> This is how investors see you.
          </div>
          <Link to="/settings" className="text-sm font-medium text-brand hover:underline">Edit in Settings →</Link>
        </div>

        {/* Stats row */}
        <div className="grid gap-4 sm:grid-cols-5">
          <Stat label="Profile views" value={stats.profileViews} />
          <Stat label="Shortlisted" value={stats.shortlisted} />
          <Stat label="Invitations" value={stats.invitations} />
          <Stat label="Accepted" value={stats.accepted} />
          <Stat label="Declined" value={stats.declined} />
        </div>

        {/* Projects */}
        {companies.length === 0 ? (
          <section className={CARD}>
            <div className="rounded-xl border border-dashed border-border p-8 text-center">
              <Building2 className="mx-auto h-8 w-8 text-brand" />
              <div className="mt-3 font-display text-lg font-semibold">No companies yet</div>
              <p className="mt-1 text-sm text-muted-foreground">
                <Link to="/companies" className="text-brand hover:underline">Add a start-up</Link> so investors have something to evaluate.
              </p>
            </div>
          </section>
        ) : (
          companies.map((c) => (
            <section key={c.id} className={CARD}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="font-display text-2xl font-semibold tracking-tight">{c.name}</h2>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <Badge variant="outline" className="border-border">{c.industry === "Other" ? c.otherIndustry : c.industry}</Badge>
                    {c.location ? <Badge variant="outline" className="border-border">{c.location}</Badge> : null}
                  </div>
                </div>
              </div>
              {c.oneLiner ? <p className="mt-4 text-sm leading-relaxed text-foreground">{c.oneLiner}</p> : null}
              {c.website ? (
                <div className="mt-4">
                  <a href={c.website} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-3 py-1 text-xs text-muted-foreground hover:text-brand hover:border-brand/40">
                    <Globe className="h-3 w-3" /> {c.website.replace(/^https?:\/\//, "")}
                  </a>
                </div>
              ) : null}
            </section>
          ))
        )}

        {/* Founder card */}
        <section className={CARD}>
          <div className="flex flex-wrap items-start gap-4">
            <div className="grid h-14 w-14 shrink-0 place-items-center rounded-full border border-border bg-brand/5 font-display text-lg font-semibold">
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-display text-xl font-semibold">{user.displayName ?? user.email}</h3>
              <div className="mt-1 text-sm text-muted-foreground">{user.location ?? "Location not set"}</div>
              {user.bio ? <p className="mt-3 text-sm leading-relaxed text-foreground">{user.bio}</p> : (
                <p className="mt-3 text-sm italic text-muted-foreground">Add a bio in Settings so investors know what you're about.</p>
              )}
              <div className="mt-4 flex flex-wrap gap-2">
                <a href={`mailto:${user.email}`} className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-3 py-1 text-xs text-muted-foreground hover:text-brand hover:border-brand/40">
                  <Mail className="h-3 w-3" /> {user.email}
                </a>
              </div>
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="mt-1 font-display text-2xl font-semibold">{value}</div>
    </div>
  );
}
