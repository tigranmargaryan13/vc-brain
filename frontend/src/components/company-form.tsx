import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Upload } from "lucide-react";
import { cn } from "@/lib/utils";

const INDUSTRIES = [
  "AI/ML", "Fintech", "Climate", "Healthtech", "Dev Tools", "Consumer",
  "Deep Tech", "Biotech", "Cybersecurity", "SaaS", "Other",
];

export type CompanyFormValue = {
  name: string;
  industry: string;
  otherIndustry?: string;
  pitchDeckName: string;
  website?: string;
  location?: string;
  oneLiner?: string;
  notes?: string;
  deckUrl?: string;
};

export function CompanyForm({
  initial,
  onSubmit,
  submitLabel = "Save company",
  secondary,
  submitting,
}: {
  initial?: Partial<CompanyFormValue>;
  onSubmit: (v: CompanyFormValue) => void | Promise<void>;
  submitLabel?: string;
  secondary?: { label: string; onClick: () => void };
  submitting?: boolean;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [industry, setIndustry] = useState(initial?.industry ?? "");
  const [otherIndustry, setOtherIndustry] = useState(initial?.otherIndustry ?? "");
  const [pitchDeckName, setPitchDeckName] = useState<string | undefined>(initial?.pitchDeckName);
  const [website, setWebsite] = useState(initial?.website ?? "");
  const [location, setLocation] = useState(initial?.location ?? "");
  const [oneLiner, setOneLiner] = useState(initial?.oneLiner ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [deckUrl, setDeckUrl] = useState(initial?.deckUrl ?? "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initial) {
      setName(initial.name ?? "");
      setIndustry(initial.industry ?? "");
      setOtherIndustry(initial.otherIndustry ?? "");
      setPitchDeckName(initial.pitchDeckName);
      setWebsite(initial.website ?? "");
      setLocation(initial.location ?? "");
      setOneLiner(initial.oneLiner ?? "");
      setNotes(initial.notes ?? "");
      setDeckUrl(initial.deckUrl ?? "");
    }
  }, [initial]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!pitchDeckName) return setError("A pitch deck (PDF) is required.");
    if (!name.trim()) return setError("Company name is required.");
    if (!industry) return setError("Industry is required.");
    if (industry === "Other" && !otherIndustry.trim())
      return setError("Please tell us your industry.");
    setError(null);
    void onSubmit({
      name: name.trim(),
      industry,
      otherIndustry: industry === "Other" ? otherIndustry.trim() : undefined,
      pitchDeckName,
      website: website.trim() || undefined,
      location: location.trim() || undefined,
      oneLiner: oneLiner.trim() || undefined,
      notes: notes.trim() || undefined,
      deckUrl: deckUrl.trim() || undefined,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="space-y-2">
        <Label htmlFor="deck">Pitch deck (PDF) <span className="text-brand">*</span></Label>
        <label
          htmlFor="deck"
          className={cn(
            "flex cursor-pointer items-center justify-between rounded-lg border border-dashed px-4 py-3 text-sm transition",
            pitchDeckName
              ? "border-brand/60 bg-gradient-brand/10 text-foreground"
              : "border-border/70 bg-surface-elevated/40 text-muted-foreground hover:border-brand/60 hover:text-foreground",
          )}
        >
          <span className="flex items-center gap-2">
            <Upload className="h-4 w-4" />
            {pitchDeckName ?? "Upload PDF"}
          </span>
          {pitchDeckName ? <span className="font-mono text-xs text-brand">Selected</span> : null}
        </label>
        <input
          id="deck"
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) setPitchDeckName(f.name);
          }}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="cname">Company name <span className="text-brand">*</span></Label>
          <Input id="cname" value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme Labs" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="cindustry">Industry <span className="text-brand">*</span></Label>
          <Select value={industry} onValueChange={setIndustry}>
            <SelectTrigger id="cindustry"><SelectValue placeholder="Select industry" /></SelectTrigger>
            <SelectContent>
              {INDUSTRIES.map((s) => (
                <SelectItem key={s} value={s}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {industry === "Other" ? (
            <Input
              className="mt-2"
              placeholder="What industry?"
              value={otherIndustry}
              onChange={(e) => setOtherIndustry(e.target.value)}
            />
          ) : null}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="cwebsite">Website</Label>
          <Input id="cwebsite" type="url" value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="https://acme.ai" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="cloc">Location</Label>
          <Input id="cloc" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Berlin" />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="coneliner">One-line description</Label>
        <Input id="coneliner" value={oneLiner} onChange={(e) => setOneLiner(e.target.value)} placeholder="We build X for Y so that Z." maxLength={160} />
      </div>

      <div className="space-y-2">
        <Label htmlFor="cdeckurl">Deck URL <span className="text-xs text-muted-foreground">(optional — link to a hosted deck)</span></Label>
        <Input id="cdeckurl" type="url" value={deckUrl} onChange={(e) => setDeckUrl(e.target.value)} placeholder="https://docsend.com/…" />
      </div>

      <div className="space-y-2">
        <Label htmlFor="cnotes">Notes</Label>
        <Textarea id="cnotes" value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="Traction, team, why now — anything else." />
      </div>


      {error ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive-foreground">{error}</div>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row-reverse">
        <Button type="submit" disabled={submitting} className="w-full bg-gradient-brand text-primary-foreground shadow-glow hover:opacity-90 sm:w-auto">
          {submitting ? "Saving…" : submitLabel}
        </Button>
        {secondary ? (
          <Button type="button" variant="ghost" onClick={secondary.onClick} className="w-full sm:w-auto">
            {secondary.label}
          </Button>
        ) : null}
      </div>
    </form>
  );
}
