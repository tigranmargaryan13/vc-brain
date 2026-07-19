import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { AuthShell, PersonaPicker } from "@/components/auth-shell";
import { CompanyForm, type CompanyFormValue } from "@/components/company-form";
import { completeSignUp, addCompany, type Persona } from "@/lib/api";
import { toast } from "sonner";

export const Route = createFileRoute("/signup")({
  component: SignupPage,
});

function SignupPage() {
  const navigate = useNavigate();
  const [persona, setPersona] = useState<Persona | null>(null);
  const [step, setStep] = useState<"persona" | "founderCompany">("persona");
  const [submitting, setSubmitting] = useState(false);

  async function createAccount(persona: Persona, company?: CompanyFormValue) {
    setSubmitting(true);
    try {
      const suffix = Math.random().toString(36).slice(2, 7);
      const email = `demo-${persona}-${suffix}@vcbrain.local`;
      await completeSignUp({
        email,
        password: "demo-password",
        persona,
        onboarding: { interests: [] },
      });
      if (company) {
        try { await addCompany(company); } catch { /* non-fatal */ }
      }
      toast.success("Demo account created.");
      navigate({ to: "/dashboard" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create account.");
      setSubmitting(false);
    }
  }

  function onPersonaContinue() {
    if (!persona || submitting) return;
    if (persona === "founder") {
      setStep("founderCompany");
    } else {
      void createAccount(persona);
    }
  }

  if (step === "founderCompany" && persona === "founder") {
    return (
      <AuthShell
        title="Tell us about your start-up"
        subtitle="Upload a pitch deck and the basics — investors will see this profile. You can add it later if you prefer."
      >
        <CompanyForm
          onSubmit={(v) => createAccount("founder", v)}
          submitLabel={submitting ? "Creating account…" : "Create account"}
          submitting={submitting}
          secondary={{
            label: "Add later",
            onClick: () => void createAccount("founder"),
          }}
        />
        <button
          type="button"
          onClick={() => setStep("persona")}
          className="mt-4 text-sm text-muted-foreground hover:text-brand"
        >
          ← Back
        </button>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Create your VC Brain account"
      subtitle="Pick a persona — we'll spin up a demo account instantly. No email or password needed."
    >
      <PersonaPicker value={persona} onChange={setPersona} onContinue={onPersonaContinue} />
      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link to="/login" className="text-brand hover:underline">
          Log in
        </Link>
      </p>
    </AuthShell>
  );
}
