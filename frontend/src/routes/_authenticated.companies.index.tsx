import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { listCompanies, addCompany, type Company } from "@/lib/api";
import { CompanyForm } from "@/components/company-form";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Plus, Building2 } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/_authenticated/companies/")({
  component: CompaniesPage,
});

function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => { listCompanies().then(setCompanies); }, []);

  async function onCreate(v: Parameters<typeof addCompany>[0]) {
    setSaving(true);
    try { const c = await addCompany(v); setCompanies((prev) => [...(prev ?? []), c]); setOpen(false); toast.success("Company added."); }
    catch (e) { toast.error(e instanceof Error ? e.message : "Failed"); }
    finally { setSaving(false); }
  }

  return (
    <AppShell title="My Companies">
      <div className="space-y-6">
        <div className="flex justify-end">
          <Button onClick={() => setOpen(true)} className="bg-gradient-brand text-primary-foreground shadow-glow"><Plus className="mr-1 h-4 w-4" />Add start-up</Button>
        </div>
        {!companies || companies.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/60 p-12 text-center">
            <Building2 className="mx-auto h-8 w-8 text-brand" />
            <div className="mt-3 font-display text-lg font-semibold">No companies yet</div>
            <p className="mt-1 text-sm text-muted-foreground">Add your first start-up so investors can discover you.</p>
            <Button className="mt-4 bg-gradient-brand text-primary-foreground shadow-glow" onClick={() => setOpen(true)}><Plus className="mr-1 h-4 w-4" />Add start-up</Button>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {companies.map((c) => (
              <Link key={c.id} to="/companies/$id" params={{ id: c.id }}
                className="group rounded-2xl border border-border/60 bg-surface/60 p-5 backdrop-blur transition hover:border-brand/40 hover:shadow-glow">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-display text-lg font-semibold group-hover:text-brand">{c.name}</div>
                    <Badge variant="outline" className="mt-1 border-border/60 text-[10px] uppercase tracking-widest">
                      {c.industry === "Other" ? c.otherIndustry : c.industry}
                    </Badge>
                  </div>
                </div>
                {c.oneLiner ? <p className="mt-3 text-sm text-muted-foreground">{c.oneLiner}</p> : null}
                <div className="mt-3 flex gap-3 text-xs text-muted-foreground">
                  {c.location ? <span>{c.location}</span> : null}
                  {c.website ? <a href={c.website} target="_blank" rel="noreferrer" className="text-brand hover:underline">{c.website.replace(/^https?:\/\//, "")}</a> : null}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>Add a start-up</DialogTitle></DialogHeader>
          <CompanyForm onSubmit={onCreate} submitLabel="Add company" submitting={saving} />
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
