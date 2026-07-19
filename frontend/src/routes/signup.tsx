import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { AuthShell, PersonaPicker } from "@/components/auth-shell";
import { completeSignUp, type Persona } from "@/lib/api";
import { toast } from "sonner";

export const Route = createFileRoute("/signup")({
  component: SignupPage,
});

function SignupPage() {
  const navigate = useNavigate();
  const [persona, setPersona] = useState<Persona | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function finalize() {
    if (!persona || submitting) return;
    setSubmitting(true);
    try {
      // Fake one-click registration — generate a throwaway demo account.
      const suffix = Math.random().toString(36).slice(2, 7);
      const email = `demo-${persona}-${suffix}@vcbrain.local`;
      await completeSignUp({
        email,
        password: "demo-password",
        persona,
        onboarding: { interests: [] },
      });
      toast.success("Demo account created.");
      navigate({ to: "/dashboard" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create account.");
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Create your VC Brain account"
      subtitle="Pick a persona — we'll spin up a demo account instantly. No email or password needed."
    >
      <PersonaPicker value={persona} onChange={setPersona} onContinue={finalize} />
      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link to="/login" className="text-brand hover:underline">
          Log in
        </Link>
      </p>
    </AuthShell>
  );
}
