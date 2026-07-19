import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { AuthShell, PersonaPicker } from "@/components/auth-shell";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { logIn, type Persona } from "@/lib/api";
import { toast } from "sonner";

export const Route = createFileRoute("/login")({
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<"persona" | "credentials">("persona");
  const [persona, setPersona] = useState<Persona | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const passwordValid = password.length >= 8;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!persona) return;
    if (!emailValid) return setError("Enter a valid email address.");
    if (!passwordValid) return setError("Password must be at least 8 characters.");
    setSubmitting(true);
    setError(null);
    try {
      await logIn({ email, password, persona });
      toast.success("Welcome back.");
      navigate({ to: "/dashboard" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title={step === "persona" ? "Log in to VC Brain" : "Welcome back"}
      subtitle={
        step === "persona"
          ? "Choose how you use VC Brain."
          : `Signing in as ${persona === "investor" ? "an investor" : "a founder"}.`
      }
    >
      {step === "persona" ? (
        <PersonaPicker
          value={persona}
          onChange={setPersona}
          onContinue={() => setStep("credentials")}
        />
      ) : (
        <form onSubmit={onSubmit} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@fund.com"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              required
            />
          </div>
          {error ? (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive-foreground">
              {error}
            </div>
          ) : null}
          <div className="flex flex-col gap-3 sm:flex-row-reverse">
            <Button
              type="submit"
              disabled={submitting}
              className="w-full bg-gradient-brand text-primary-foreground shadow-glow hover:opacity-90 sm:w-auto"
            >
              {submitting ? "Signing in…" : "Log in"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setStep("persona")}
              className="w-full sm:w-auto"
            >
              Back
            </Button>
          </div>
          <p className="text-center text-sm text-muted-foreground">
            No account yet?{" "}
            <Link to="/signup" className="text-brand hover:underline">
              Sign up
            </Link>
          </p>
        </form>
      )}
    </AuthShell>
  );
}
