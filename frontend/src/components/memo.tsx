import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Memo, MemoSection } from "@/lib/mock-data";
import { ScoreTriad, ClaimLine } from "@/components/scores";

function verdictStyles(v: Memo["verdict"]) {
  switch (v) {
    case "Strong yes": return "border-emerald-500/50 bg-emerald-500/10 text-emerald-300";
    case "Conditional yes": return "border-brand/50 bg-gradient-brand/15 text-foreground";
    case "Watch": return "border-amber-500/50 bg-amber-500/10 text-amber-300";
    case "Pass": return "border-rose-500/50 bg-rose-500/10 text-rose-300";
  }
}

function Section({ section }: { section: MemoSection }) {
  const [open, setOpen] = useState(true);
  return (
    <section className="rounded-2xl border border-border/60 bg-surface/60 p-5 backdrop-blur">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-left"
      >
        <h3 className="font-display text-base font-semibold">{section.title}</h3>
        {open ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
      </button>
      {open ? (
        <div className="mt-4 space-y-3">
          {section.paragraph ? <p className="text-sm text-muted-foreground">{section.paragraph}</p> : null}
          {section.bullets ? (
            <div className="space-y-2">
              {section.bullets.map((c, i) => <ClaimLine key={i} claim={c} />)}
            </div>
          ) : null}
          {section.swot ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {(["S", "W", "O", "T"] as const).map((k) => (
                <div key={k}>
                  <div className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-brand">
                    {k === "S" ? "Strengths" : k === "W" ? "Weaknesses" : k === "O" ? "Opportunities" : "Threats"}
                  </div>
                  <div className="space-y-2">
                    {section.swot![k].map((c, i) => <ClaimLine key={i} claim={c} />)}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          {section.gaps ? (
            <ul className="space-y-1.5 text-sm">
              {section.gaps.map((g, i) => (
                <li key={i} className="flex gap-2 text-muted-foreground">
                  <span className="text-amber-400">•</span> {g}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export function MemoView({ memo }: { memo: Memo }) {
  return (
    <div className="space-y-4">
      <div className={cn("sticky top-16 z-10 rounded-2xl border p-5 backdrop-blur-xl", verdictStyles(memo.verdict))}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest opacity-80">Verdict</div>
            <div className="mt-1 font-display text-2xl font-semibold">{memo.verdict}</div>
          </div>
          <ScoreTriad scores={memo.scoresRestated} />
        </div>
        <ul className="mt-4 space-y-1.5 text-sm">
          {memo.topReasons.map((r, i) => (
            <li key={i} className="flex gap-2"><span className="text-brand">▸</span>{r}</li>
          ))}
        </ul>
      </div>
      {memo.sections.map((s) => <Section key={s.id} section={s} />)}
    </div>
  );
}
