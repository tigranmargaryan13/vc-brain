import { cn } from "@/lib/utils";
import { ArrowUpRight, ArrowRight, ArrowDownRight, ShieldAlert, Sparkles, ExternalLink } from "lucide-react";
import type { Trend, MarketRating, FitRating, TrustLevel, TrustState, Claim, ScoreDimension } from "@/lib/mock-data";

function TrendIcon({ trend, className }: { trend: Trend; className?: string }) {
  const Icon = trend === "up" ? ArrowUpRight : trend === "down" ? ArrowDownRight : ArrowRight;
  const color = trend === "up" ? "text-emerald-600" : trend === "down" ? "text-rose-600" : "text-muted-foreground";
  return <Icon className={cn("h-3.5 w-3.5", color, className)} aria-label={`trend ${trend}`} />;
}

export function FounderMeter({
  value,
  trend,
  confidence,
  band,
}: {
  value: number;
  trend: Trend;
  confidence?: number;
  band?: [number, number];
}) {
  return (
    <div className="min-w-[11rem] space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Founder</span>
        <span className="flex items-center gap-1 font-mono text-xs text-foreground">
          {value}
          <TrendIcon trend={trend} />
        </span>
      </div>
      <div className="relative h-1.5 w-full rounded-full bg-muted">
        {band ? (
          <div
            className="absolute inset-y-0 rounded-full bg-brand/25"
            style={{
              left: `${Math.max(0, Math.min(100, band[0]))}%`,
              width: `${Math.max(2, Math.min(100, band[1] - band[0]))}%`,
            }}
          />
        ) : null}
        <div
          className="relative h-full rounded-full bg-brand"
          style={{ width: `${Math.max(4, Math.min(100, value))}%` }}
        />
      </div>
      {band || typeof confidence === "number" ? (
        <div className="font-mono text-[10px] text-muted-foreground">
          {band ? `band ${band[0]}–${band[1]}` : null}
          {band && typeof confidence === "number" ? " · " : null}
          {typeof confidence === "number" ? `confidence ${confidence.toFixed(2)}` : null}
        </div>
      ) : null}
    </div>
  );
}

export function MarketChip({ value, trend }: { value: MarketRating; trend: Trend }) {
  const styles =
    value === "Bullish"
      ? "border-emerald-600/30 bg-emerald-50 text-emerald-700"
      : value === "Bear"
        ? "border-rose-600/30 bg-rose-50 text-rose-700"
        : "border-border bg-muted text-muted-foreground";
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
      ? "border-brand/40 bg-brand/5 text-brand"
      : value === "At risk"
        ? "border-rose-600/30 bg-rose-50 text-rose-700"
        : "border-amber-600/30 bg-amber-50 text-amber-700";
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

export function ScoreTriad({
  scores,
}: {
  scores: {
    founder: number;
    founderTrend: Trend;
    market: MarketRating;
    marketTrend: Trend;
    fit: FitRating;
    fitTrend: Trend;
    confidence?: number;
    band?: [number, number];
  };
}) {
  return (
    <div className="flex flex-wrap items-end gap-6">
      <FounderMeter value={scores.founder} trend={scores.founderTrend} confidence={scores.confidence} band={scores.band} />
      <MarketChip value={scores.market} trend={scores.marketTrend} />
      <FitChip value={scores.fit} trend={scores.fitTrend} />
    </div>
  );
}

export function ScoreDimensionsBreakdown({ dimensions }: { dimensions: ScoreDimension[] }) {
  return (
    <div className="space-y-3">
      <div className="space-y-2">
        {dimensions.map((d) => {
          const value = Math.max(0, Math.min(100, d.value));
          const coverage = Math.max(0, Math.min(1, d.coverage));
          const opacity = 0.2 + coverage * 0.8;
          const weightPct = d.weight <= 1 ? Math.round(d.weight * 100) : Math.round(d.weight);
          return (
            <div key={d.name} className="grid grid-cols-[8rem_1fr_auto] items-center gap-3">
              <div className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">{d.name}</div>
              <div className="h-2 w-full rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-brand"
                  style={{ width: `${Math.max(2, value)}%`, opacity }}
                />
              </div>
              <div className="w-28 text-right font-mono text-[10px] text-muted-foreground">
                {value} · ×{weightPct}%
              </div>
            </div>
          );
        })}
      </div>
      <p className="font-mono text-[10px] text-muted-foreground">
        Faint bars = little data — missing data widens the band, it never penalizes.
      </p>
    </div>
  );
}

export function ColdStartBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-brand/40 bg-brand/5 px-2.5 py-1 text-xs text-brand">
      <Sparkles className="h-3 w-3" />
      Cold start — unknowns are NOT negatives
    </span>
  );
}

export function ContradictionBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-600/40 bg-rose-50 px-2.5 py-1 text-xs text-rose-700">
      <ShieldAlert className="h-3 w-3" />
      Contradicted claim
    </span>
  );
}

export function TrustChip({ trust, state, sourceUrl, sourceLabel }: { trust: TrustLevel; state: TrustState; sourceUrl: string; sourceLabel: string }) {
  const trustColor =
    trust === "High"
      ? "border-emerald-600/30 text-emerald-700"
      : trust === "Medium"
        ? "border-brand/40 text-brand"
        : "border-border text-muted-foreground";
  const stateColor =
    state === "contradicted"
      ? "border-rose-600/40 bg-rose-50 text-rose-700"
      : state === "corroborated"
        ? "border-emerald-600/30 bg-emerald-50/60 text-emerald-700"
        : "border-border bg-muted text-muted-foreground";
  return (
    <span className="inline-flex flex-wrap items-center gap-1 font-mono text-[10px] uppercase tracking-widest">
      <span className={cn("rounded-full border px-1.5 py-0.5", trustColor)}>Trust: {trust}</span>
      <span className={cn("rounded-full border px-1.5 py-0.5", stateColor)}>{state}</span>
      <a
        href={sourceUrl}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-0.5 rounded-full border border-border bg-muted px-1.5 py-0.5 text-muted-foreground hover:text-brand"
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
          ? "border-rose-600/40 bg-rose-50/60"
          : unknown
            ? "border-dashed border-border bg-muted/40"
            : "border-border bg-muted/30",
      )}
    >
      <p className={cn("text-sm", unknown ? "italic text-muted-foreground" : "text-foreground")}>
        {unknown ? `${claim.text} — unknown, not counted against.` : claim.text}
      </p>
      <TrustChip trust={claim.trust} state={claim.state} sourceUrl={claim.sourceUrl} sourceLabel={claim.sourceLabel} />
    </div>
  );
}
