import { Link } from "@tanstack/react-router";
import { Brain, Briefcase, Rocket, ArrowRight } from "lucide-react";
import type { Persona } from "@/lib/api";
import { cn } from "@/lib/utils";

export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-hero text-foreground">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link to="/" className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-brand shadow-glow">
            <Brain className="h-4 w-4 text-primary-foreground" />
          </span>
          <span className="font-display text-lg font-semibold tracking-tight">VC Brain</span>
        </Link>
      </header>
      <main className="mx-auto flex max-w-xl flex-col px-6 pb-16 pt-8">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
          {subtitle ? (
            <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>
          ) : null}
        </div>
        <div className="rounded-2xl border border-border/60 bg-surface/70 p-6 backdrop-blur-xl sm:p-8">
          {children}
        </div>
      </main>
    </div>
  );
}

export function PersonaPicker({
  value,
  onChange,
  onContinue,
}: {
  value: Persona | null;
  onChange: (p: Persona) => void;
  onContinue: () => void;
}) {
  const options: {
    key: Persona;
    title: string;
    body: string;
    icon: React.ComponentType<{ className?: string }>;
  }[] = [
    {
      key: "investor",
      title: "I'm an Investor",
      body: "Turn a thesis into a ranked founder pipeline.",
      icon: Briefcase,
    },
    {
      key: "founder",
      title: "I'm a Founder",
      body: "Get discovered by aligned investors and accelerators.",
      icon: Rocket,
    },
  ];
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        {options.map((o) => {
          const Icon = o.icon;
          const selected = value === o.key;
          return (
            <button
              key={o.key}
              type="button"
              onClick={() => onChange(o.key)}
              className={cn(
                "group relative rounded-xl border p-5 text-left transition",
                selected
                  ? "border-brand bg-gradient-brand/10 shadow-glow"
                  : "border-border/60 bg-surface-elevated/40 hover:border-brand/50",
              )}
            >
              <div
                className={cn(
                  "mb-4 grid h-10 w-10 place-items-center rounded-lg ring-1 transition",
                  selected
                    ? "bg-gradient-brand text-primary-foreground ring-brand"
                    : "bg-gradient-brand/20 text-brand ring-brand/40",
                )}
              >
                <Icon className="h-5 w-5" />
              </div>
              <div className="font-display text-base font-semibold">{o.title}</div>
              <div className="mt-1 text-sm text-muted-foreground">{o.body}</div>
            </button>
          );
        })}
      </div>
      <button
        type="button"
        disabled={!value}
        onClick={onContinue}
        className={cn(
          "inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition",
          value
            ? "bg-gradient-brand text-primary-foreground shadow-glow hover:opacity-90"
            : "cursor-not-allowed bg-muted text-muted-foreground",
        )}
      >
        Continue
        <ArrowRight className="h-4 w-4" />
      </button>
    </div>
  );
}
