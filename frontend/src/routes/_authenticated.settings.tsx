import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  getCurrentUser, updateProfile, changePassword, deleteAccount, logOut,
  getNotificationPrefs, updateNotificationPrefs, type User, type NotificationPrefs,
} from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/settings")({
  component: SettingsPage,
});

const SECTORS = ["AI/ML", "Fintech", "Climate", "Healthtech", "Dev Tools", "Consumer", "Deep Tech", "Biotech", "Cybersecurity", "SaaS"];
const STAGES = ["Pre-seed", "Seed", "Series A"];

function SettingsPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [location, setLocation] = useState("");
  const [bio, setBio] = useState("");
  const [links, setLinks] = useState("");
  const [interests, setInterests] = useState<string[]>([]);
  const [curPw, setCurPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [prefs, setPrefs] = useState<NotificationPrefs | null>(null);

  useEffect(() => {
    getCurrentUser().then((u) => {
      if (!u) return;
      setUser(u);
      setDisplayName(u.displayName ?? "");
      setLocation(u.location ?? "");
      setBio(u.bio ?? "");
      setLinks(u.links ?? "");
      setInterests(u.onboarding?.interests ?? []);
    });
    getNotificationPrefs().then(setPrefs);
  }, []);

  if (!user || !prefs) return <AppShell title="Settings"><div className="text-muted-foreground">Loading…</div></AppShell>;

  function toggleInterest(s: string) {
    setInterests((prev) => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);
  }

  async function saveProfile() {
    const patch: Parameters<typeof updateProfile>[0] = { displayName, location, bio, links };
    if (user!.persona === "investor") {
      patch.onboarding = { ...(user!.onboarding ?? { interests: [] }), interests };
    }
    const u = await updateProfile(patch);
    setUser(u);
    toast.success("Profile saved.");
  }
  async function savePassword() {
    try { await changePassword({ current: curPw, next: newPw }); setCurPw(""); setNewPw(""); toast.success("Password updated."); }
    catch (e) { toast.error(e instanceof Error ? e.message : "Failed"); }
  }
  async function savePrefs(next: NotificationPrefs) {
    const p = await updateNotificationPrefs(next); setPrefs(p); toast.success("Preferences updated.");
  }
  async function onDelete() {
    await deleteAccount(); toast("Account deleted."); navigate({ to: "/" });
  }

  return (
    <AppShell title="Profile & Settings">
      <div className="space-y-6">
        <Section title="Profile">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2"><Label>Display name</Label><Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} /></div>
            <div className="space-y-2"><Label>Email</Label>
              <div className="flex items-center gap-2"><Input value={user.email} readOnly /><Badge variant="outline" className="border-brand/40 text-brand uppercase text-[10px] tracking-widest">{user.persona}</Badge></div>
            </div>
            {user.persona === "founder" ? (
              <>
                <div className="space-y-2"><Label>Location</Label><Input value={location} onChange={(e) => setLocation(e.target.value)} /></div>
                <div className="space-y-2"><Label>Links (comma-separated)</Label><Input value={links} onChange={(e) => setLinks(e.target.value)} placeholder="linkedin.com/…, twitter.com/…" /></div>
                <div className="space-y-2 sm:col-span-2"><Label>Bio</Label><Textarea value={bio} onChange={(e) => setBio(e.target.value)} rows={3} /></div>
              </>
            ) : (
              <div className="sm:col-span-2">
                <Label className="font-mono text-[10px] uppercase tracking-widest text-brand">Interests</Label>
                <div className="mt-2 flex flex-wrap gap-2">
                  {[...SECTORS, ...STAGES].map(s => (
                    <button key={s} type="button" onClick={() => toggleInterest(s)}
                      className={cn("rounded-full border px-3 py-1 text-sm transition", interests.includes(s) ? "border-brand bg-gradient-brand/20 text-foreground shadow-glow" : "border-border/60 bg-surface-elevated/40 text-muted-foreground hover:border-brand/40")}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
          <div className="mt-4"><Button className="bg-gradient-brand text-primary-foreground shadow-glow" onClick={saveProfile}>Save profile</Button></div>
        </Section>

        <Section title="Security">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2"><Label>Current password</Label><Input type="password" value={curPw} onChange={(e) => setCurPw(e.target.value)} /></div>
            <div className="space-y-2"><Label>New password</Label><Input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} /></div>
          </div>
          <div className="mt-4"><Button onClick={savePassword}>Change password</Button></div>
        </Section>

        <Section title="Notification preferences">
          <div className="space-y-3">
            <PrefRow label="Best-match alerts" desc="When new founders match your thesis." checked={prefs.bestMatchAlerts} onChange={(v) => savePrefs({ ...prefs, bestMatchAlerts: v })} />
            <PrefRow label="Invitations" desc="Investor outreach / founder responses." checked={prefs.invitations} onChange={(v) => savePrefs({ ...prefs, invitations: v })} />
            <PrefRow label="Weekly email digest" desc="A Monday summary in your inbox." checked={prefs.emailDigest} onChange={(v) => savePrefs({ ...prefs, emailDigest: v })} />
          </div>
        </Section>

        <Section title="Account">
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={async () => { await logOut(); navigate({ to: "/" }); }}>Log out</Button>
            <AlertDialog>
              <AlertDialogTrigger asChild><Button variant="destructive">Delete account</Button></AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete this account?</AlertDialogTitle>
                  <AlertDialogDescription>This removes only your {user.persona} account. Any other account you have under the same email will be untouched.</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={onDelete} className="bg-destructive text-destructive-foreground">Delete</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </Section>
      </div>
    </AppShell>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-border/60 bg-surface/60 p-6 backdrop-blur">
      <h2 className="mb-4 font-display text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}
function PrefRow({ label, desc, checked, onChange }: { label: string; desc: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border/60 bg-surface-elevated/40 p-3">
      <div>
        <div className="text-sm font-medium">{label}</div>
        <div className="text-xs text-muted-foreground">{desc}</div>
      </div>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}
