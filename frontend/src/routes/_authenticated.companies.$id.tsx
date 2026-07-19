import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { getCompany, updateCompany, type Company } from "@/lib/api";
import { CompanyForm } from "@/components/company-form";
import { toast } from "sonner";
import { ArrowLeft } from "lucide-react";

export const Route = createFileRoute("/_authenticated/companies/$id")({
  component: CompanyDetail,
});

function CompanyDetail() {
  const { id } = Route.useParams();
  const navigate = useNavigate();
  const [c, setC] = useState<Company | null | undefined>(undefined);
  const [saving, setSaving] = useState(false);

  useEffect(() => { getCompany(id).then(setC); }, [id]);

  if (c === undefined) return <AppShell title="Company"><div className="text-muted-foreground">Loading…</div></AppShell>;
  if (!c) return <AppShell title="Company"><div className="text-muted-foreground">Not found. <Link to="/companies" className="text-brand">Back</Link></div></AppShell>;

  async function onSave(v: Parameters<typeof updateCompany>[1]) {
    setSaving(true);
    try { const updated = await updateCompany(id, v); setC(updated); toast.success("Company updated."); }
    catch (e) { toast.error(e instanceof Error ? e.message : "Failed"); }
    finally { setSaving(false); }
  }

  return (
    <AppShell title={c.name}>
      <div className="mb-4">
        <button onClick={() => navigate({ to: "/companies" })} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-brand">
          <ArrowLeft className="h-3.5 w-3.5" /> Back to companies
        </button>
      </div>
      <div className="rounded-2xl border border-border/60 bg-surface/60 p-6 backdrop-blur">
        <CompanyForm initial={c} onSubmit={onSave} submitLabel="Save changes" submitting={saving} />
      </div>
    </AppShell>
  );
}
