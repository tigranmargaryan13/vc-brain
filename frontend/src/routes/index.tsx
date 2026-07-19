import { createFileRoute, Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import {
  Brain,
  Target,
  Search,
  Gauge,
  ListOrdered,
  Send,
  FileText,
  ShieldCheck,
  Sparkles,
  GitBranch,
  TrendingUp,
} from "lucide-react";

export const Route = createFileRoute("/")({
  component: Landing,
});

const pipeline = [
  { icon: Target, label: "Thesis" },
  { icon: Search, label: "Source" },
  { icon: Gauge, label: "Score" },
  { icon: ListOrdered, label: "Rank" },
  { icon: Send, label: "Outreach" },
  { icon: FileText, label: "Memo" },
];

const values = [
  {
    icon: Sparkles,
    title: "Cold-start friendly signals",
    body: "We surface founders from public signals — commits, papers, launches, hiring — long before they show up in a deal-flow database.",
  },
  {
    icon: ShieldCheck,
    title: "Per-claim trust scores",
    body: "Every fact in a memo carries a provenance-backed confidence score. No hallucinated bullet points, no unsourced claims.",
  },
  {
    icon: GitBranch,
    title: "Full traceability",
    body: "Click any score or sentence and see the exact sources, timestamps, and reasoning steps that produced it.",
  },
  {
    icon: TrendingUp,
    title: "Power-law aware ranking",
    body: "Optimized for outlier detection, not average fit. The ranker is tuned to elevate the 1-in-1000, not the merely reasonable.",
  },
];

function Landing() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Nav */}
      <header className="sticky top-0 z-40 border-b border-border/60 bg-background/70 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Link to="/" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-brand shadow-glow">
              <Brain className="h-4 w-4 text-primary-foreground" />
            </span>
            <span className="font-display text-lg font-semibold tracking-tight">VC Brain</span>
          </Link>
          <nav className="flex items-center gap-2">
            <Button asChild variant="ghost" size="sm">
              <Link to="/login">Log in</Link>
            </Button>
            <Button asChild size="sm" className="bg-gradient-brand text-primary-foreground hover:opacity-90">
              <Link to="/signup">Sign up</Link>
            </Button>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden bg-hero">
        <div className="absolute inset-0 grid-bg opacity-60" aria-hidden />
        <div className="relative mx-auto max-w-6xl px-6 pt-24 pb-28 text-center">
          <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-border/60 bg-surface/60 px-3 py-1 font-mono text-xs text-muted-foreground backdrop-blur">
            <span className="h-1.5 w-1.5 rounded-full bg-brand shadow-glow" />
            AI sourcing for investors &amp; accelerators
          </div>
          <h1 className="mx-auto max-w-4xl text-5xl font-semibold leading-[1.05] tracking-tight sm:text-6xl md:text-7xl">
            Find tomorrow's founders <br className="hidden sm:block" />
            <span className="text-gradient-brand">before the market does.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-base text-muted-foreground sm:text-lg">
            VC Brain turns your investment thesis into a live, ranked founder pipeline —
            sourced from public signals, scored with traceable evidence, and packaged into
            outreach and investment memos you can actually defend.
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <Button
              asChild
              size="lg"
              className="bg-gradient-brand text-primary-foreground shadow-glow hover:opacity-90"
            >
              <Link to="/signup">Sign up</Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="border-border/80 bg-surface/60">
              <Link to="/login">Log in</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Pipeline */}
      <section className="border-y border-border/60 bg-surface/40">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <div className="mb-10 text-center">
            <div className="mb-2 font-mono text-xs uppercase tracking-widest text-brand">
              The pipeline
            </div>
            <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
              From thesis to memo, in one continuous system
            </h2>
          </div>
          <ol className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {pipeline.map((step, i) => {
              const Icon = step.icon;
              return (
                <li
                  key={step.label}
                  className="group relative rounded-xl border border-border/60 bg-surface-elevated/60 p-5 backdrop-blur transition hover:border-brand/50 hover:shadow-glow"
                >
                  <div className="mb-3 flex items-center justify-between">
                    <span className="grid h-9 w-9 place-items-center rounded-lg bg-gradient-brand/20 ring-1 ring-brand/40">
                      <Icon className="h-4 w-4 text-brand" />
                    </span>
                    <span className="font-mono text-xs text-muted-foreground">
                      0{i + 1}
                    </span>
                  </div>
                  <div className="font-display text-sm font-semibold">{step.label}</div>
                </li>
              );
            })}
          </ol>
        </div>
      </section>

      {/* Value props */}
      <section className="mx-auto max-w-6xl px-6 py-24">
        <div className="mb-12 max-w-2xl">
          <div className="mb-2 font-mono text-xs uppercase tracking-widest text-brand">
            Why VC Brain
          </div>
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Built for the way outlier deals actually happen.
          </h2>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          {values.map((v) => {
            const Icon = v.icon;
            return (
              <div
                key={v.title}
                className="group relative overflow-hidden rounded-2xl border border-border/60 bg-surface/60 p-6 backdrop-blur transition hover:border-brand/40"
              >
                <div className="mb-4 grid h-10 w-10 place-items-center rounded-lg bg-gradient-brand/20 ring-1 ring-brand/40">
                  <Icon className="h-5 w-5 text-brand" />
                </div>
                <h3 className="mb-2 text-lg font-semibold">{v.title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">{v.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-border/60 bg-surface/40">
        <div className="mx-auto max-w-4xl px-6 py-20 text-center">
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Point it at your thesis. See who's building it.
          </h2>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button
              asChild
              size="lg"
              className="bg-gradient-brand text-primary-foreground shadow-glow hover:opacity-90"
            >
              <Link to="/signup">Get started</Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="border-border/80 bg-surface/60">
              <Link to="/login">I already have an account</Link>
            </Button>
          </div>
        </div>
      </section>

      <footer className="border-t border-border/60 py-8 text-center font-mono text-xs text-muted-foreground">
        © {new Date().getFullYear()} VC Brain
      </footer>
    </div>
  );
}
