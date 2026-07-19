import { Link } from "@tanstack/react-router";
import { Bookmark, BookmarkCheck, MailPlus, ShieldAlert } from "lucide-react";
import type { FounderProfile, Invitation } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScoreTriad, ColdStartBadge, ContradictionBadge } from "@/components/scores";

export function FounderCard({
  f,
  saved,
  onToggleSave,
  invite,
  onInvite,
}: {
  f: FounderProfile;
  saved: boolean;
  onToggleSave: () => void;
  invite?: Invitation;
  onInvite: () => void;
}) {
  return (
    <div className="group relative rounded-2xl border border-border/60 bg-surface/60 p-5 backdrop-blur transition hover:border-brand/40 hover:shadow-glow">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            to="/founder/$id"
            params={{ id: f.id }}
            className="font-display text-lg font-semibold tracking-tight hover:text-brand"
          >
            {f.name}
          </Link>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>{f.location}</span>
            {f.projects.map((p) => (
              <Badge key={p.id} variant="outline" className="border-border/60 text-[10px] uppercase tracking-widest">
                {p.sector} · {p.stage}
              </Badge>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <Button size="sm" variant="ghost" onClick={onToggleSave} title={saved ? "Unsave" : "Save"}>
            {saved ? <BookmarkCheck className="h-4 w-4 text-brand" /> : <Bookmark className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      <div className="mt-4 space-y-2">
        {f.projects.map((p) => (
          <p key={p.id} className="text-sm text-muted-foreground">
            <span className="text-foreground">{p.name}</span> — {p.oneLiner}
          </p>
        ))}
      </div>

      <div className="mt-5">
        <ScoreTriad scores={f.scores} />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {f.coldStart ? <ColdStartBadge /> : null}
        {f.hasContradiction ? <ContradictionBadge /> : null}
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
        <Link to="/founder/$id" params={{ id: f.id }} className="text-xs text-brand hover:underline">
          View profile →
        </Link>
        {invite && invite.status !== "sent" ? (
          <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs ${invite.status === "accepted" ? "border-emerald-500/40 text-emerald-300" : "border-rose-500/40 text-rose-300"}`}>
            {invite.status === "accepted" ? "Accepted" : "Declined"}
          </span>
        ) : invite ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-brand/40 text-brand px-2.5 py-1 text-xs">
            <ShieldAlert className="h-3 w-3" /> Invited
          </span>
        ) : (
          <Button size="sm" variant="outline" onClick={onInvite} className="border-brand/40 hover:bg-gradient-brand/10">
            <MailPlus className="mr-1.5 h-3.5 w-3.5" /> Invite to apply
          </Button>
        )}
      </div>
    </div>
  );
}
