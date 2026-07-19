import { createFileRoute, Outlet, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { getCurrentUser, type User } from "@/lib/api";

export const Route = createFileRoute("/_authenticated")({
  component: AuthenticatedLayout,
});

function AuthenticatedLayout() {
  const navigate = useNavigate();
  const [ready, setReady] = useState<User | null | undefined>(undefined);
  useEffect(() => {
    getCurrentUser().then((u) => {
      if (!u) navigate({ to: "/login" });
      else setReady(u);
    });
  }, [navigate]);
  if (ready === undefined) {
    return <div className="grid min-h-screen place-items-center bg-hero text-muted-foreground">Loading…</div>;
  }
  if (!ready) return null;
  return <Outlet />;
}
