import { cn } from "@/lib/utils";
import { ArrowUpRight, ArrowRight, ArrowDownRight, ShieldAlert, Sparkles, ExternalLink } from "lucide-react";
import type { Trend, MarketRating, FitRating, TrustLevel, TrustState, Claim } from "@/lib/mock-data";

function TrendIcon({ trend, className }: { trend: Trend; className?: string }) {
  const Icon = trend === "up" ? ArrowUpRight : trend === "down" ? ArrowDownRight : ArrowRight;
  const color = trend === "up" ? "text-emerald-400" : trend === "down" ? "text-rose-400" : "text-muted-foreground";
  return <Icon className={cn("h-3.5 w-3.5", color, className)} aria-label={`trend ${trend}`} />;
}

export function FounderMeter({ value, trend }: { value: number; trend: Trend }) {
  return (
    <div className="min-w-[9rem] space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Founder</span>
        <span className="flex items-center gap-1 font-mono text-xs text-foreground">
          {value}
          <TrendIcon trend={trend} />
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-surface-elevated">
        <div
          className="h-full rounded-full bg-gradient-brand"
          style={{ width: `${Math.max(4, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
}

export function MarketChip({ value, trend }: { value: MarketRating; trend: Trend }) {
  const styles =
    value === "Bullish"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
      : value === "Bear"
        ? "border-rose-500/40 bg-rose-500/10 text-rose-300"
        : "border-border/60 bg-surface-elevated/60 text-muted-foreground";
  return (
    <div className="space-y-1.5">
      <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Market</span>
      <div className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs", styles)}>
        {value}
        <TrendIcon trend={trend} />
      </div>
    </div>
  );
}

export function FitChip({ value, trend }: { value: FitRating; trend: Trend }) {
  const styles =
    value === "Survives as-is"
      ? "border-brand/50 bg-gradient-brand/10 text-foreground"
      : value === "At risk"
        ? "border-rose-500/40 bg-rose-500/10 text-rose-300"
        : "border-amber-500/40 bg-amber-500/10 text-amber-300";
  return (
    <div className="space-y-1.5">
      <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Idea vs. Market</span>
      <div className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs", styles)}>
        {value}
        <TrendIcon trend={trend} />
      </div>
    </div>
  );
}

export function ScoreTriad({ scores }: { scores: { founder: number; founderTrend: Trend; market: MarketRating; marketTrend: Trend; fit: FitRating; fitTrend: Trend } }) {
  return (
    <div className="flex flex-wrap items-end gap-6">
      <FounderMeter value={scores.founder} trend={scores.founderTrend} />
      <MarketChip value={scores.market} trend={scores.marketTrend} />
      <FitChip value={scores.fit} trend={scores.fitTrend} />
    </div>
  );
}

export function ColdStartBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-brand/40 bg-gradient-brand/10 px-2.5 py-1 text-xs text-brand">
      <Sparkles className="h-3 w-3" />
      Cold start — unknowns are NOT negatives
    </span>
  );
}

export function ContradictionBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-500/50 bg-rose-500/10 px-2.5 py-1 text-xs text-rose-300">
      <ShieldAlert className="h-3 w-3" />
      Contradicted claim
    </span>
  );
}

export function TrustChip({ trust, state, sourceUrl, sourceLabel }: { trust: TrustLevel; state: TrustState; sourceUrl: string; sourceLabel: string }) {
  const trustColor =
    trust === "High"
      ? "border-emerald-500/40 text-emerald-300"
      : trust === "Medium"
        ? "border-brand/40 text-brand"
        : "border-muted-foreground/40 text-muted-foreground";
  const stateColor =
    state === "contradicted"
      ? "border-rose-500/50 bg-rose-500/10 text-rose-300"
      : state === "corroborated"
        ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-300"
        : "border-border/60 bg-surface-elevated/60 text-muted-foreground";
  return (
    <span className="inline-flex flex-wrap items-center gap-1 font-mono text-[10px] uppercase tracking-widest">
      <span className={cn("rounded-full border px-1.5 py-0.5", trustColor)}>Trust: {trust}</span>
      <span className={cn("rounded-full border px-1.5 py-0.5", stateColor)}>{state}</span>
      <a
        href={sourceUrl}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-0.5 rounded-full border border-border/60 bg-surface-elevated/60 px-1.5 py-0.5 text-muted-foreground hover:text-brand"
      >
        {sourceLabel}
        <ExternalLink className="h-2.5 w-2.5" />
      </a>
    </span>
  );
}

export function ClaimLine({ claim, unknown }: { claim: Claim; unknown?: boolean }) {
  return (
    <div
      className={cn(
        "space-y-1.5 rounded-lg border p-3",
        claim.state === "contradicted"
          ? "border-rose-500/40 bg-rose-500/5"
          : unknown
            ? "border-dashed border-border/60 bg-surface-elevated/40"
            : "border-border/60 bg-surface-elevated/40",
      )}
    >
      <p className={cn("text-sm", unknown ? "italic text-muted-foreground" : "text-foreground")}>
        {unknown ? `${claim.text} — unknown, not counted against.` : claim.text}
      </p>
      <TrustChip trust={claim.trust} state={claim.state} sourceUrl={claim.sourceUrl} sourceLabel={claim.sourceLabel} />
    </div>
  );
}
