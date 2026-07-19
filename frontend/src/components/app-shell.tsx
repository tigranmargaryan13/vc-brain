import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";
import {
  Brain, Bell, LayoutDashboard, Compass, Target, Building2, LineChart, Menu, X, LogOut, Settings, User as UserIcon,
} from "lucide-react";
import {
  getCurrentUser, logOut, listNotifications, markNotificationRead, markAllNotificationsRead,
  respondToInvitation, type User, type Notification,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

type NavItem = { to: string; label: string; icon: React.ComponentType<{ className?: string }>; params?: Record<string, string> };

const INVESTOR_NAV: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/hunt", label: "Hunt Founders", icon: Compass },
  { to: "/thesis", label: "Thesis", icon: Target },
];
const FOUNDER_NAV: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/companies", label: "My Companies", icon: Building2 },
  { to: "/criteria", label: "Fundraising Criteria", icon: LineChart },
];

export function AppShell({ title, children }: { title: string; children: ReactNode }) {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [openMobile, setOpenMobile] = useState(false);
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  useEffect(() => {
    getCurrentUser().then((u) => {
      if (!u) navigate({ to: "/login" });
      else setUser(u);
    });
  }, [navigate]);

  useEffect(() => setOpenMobile(false), [pathname]);

  if (user === undefined) {
    return <div className="grid min-h-screen place-items-center text-muted-foreground">Loading…</div>;
  }
  if (!user) return null;

  const nav = user.persona === "investor" ? INVESTOR_NAV : FOUNDER_NAV;

  return (
    <div className="min-h-screen bg-hero text-foreground">
      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-border/60 bg-background/80 backdrop-blur-xl transition-transform lg:translate-x-0",
          openMobile ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
      >
        <div className="flex h-16 items-center justify-between px-5">
          <Link to="/" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-brand shadow-glow">
              <Brain className="h-4 w-4 text-primary-foreground" />
            </span>
            <span className="font-display text-lg font-semibold tracking-tight">VC Brain</span>
          </Link>
          <button className="lg:hidden" onClick={() => setOpenMobile(false)} aria-label="Close menu">
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {nav.map((item) => {
            const active = pathname === item.to || (item.to !== "/dashboard" && pathname.startsWith(item.to));
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
                  active
                    ? "bg-gradient-brand/15 text-foreground shadow-glow"
                    : "text-muted-foreground hover:bg-surface-elevated/60 hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-border/60 p-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex w-full items-center gap-3 rounded-lg p-2 text-left transition hover:bg-surface-elevated/60">
                <span className="grid h-8 w-8 place-items-center rounded-full bg-gradient-brand text-primary-foreground font-mono text-xs">
                  {user.email.slice(0, 2).toUpperCase()}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm">{user.displayName ?? user.email}</div>
                  <Badge variant="outline" className="mt-0.5 border-brand/40 text-[10px] uppercase tracking-widest text-brand">
                    {user.persona}
                  </Badge>
                </div>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" side="top" className="w-56">
              <DropdownMenuItem asChild>
                <Link to="/settings"><UserIcon className="mr-2 h-4 w-4" /> Profile & settings</Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/settings"><Settings className="mr-2 h-4 w-4" /> Preferences</Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={async () => { await logOut(); navigate({ to: "/" }); }}
              >
                <LogOut className="mr-2 h-4 w-4" /> Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border/60 bg-background/70 px-4 backdrop-blur-xl sm:px-6">
          <div className="flex items-center gap-3">
            <button className="lg:hidden" onClick={() => setOpenMobile(true)} aria-label="Open menu">
              <Menu className="h-5 w-5" />
            </button>
            <h1 className="font-display text-lg font-semibold tracking-tight">{title}</h1>
          </div>
          <NotificationBell persona={user.persona} />
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">{children}</main>
      </div>
    </div>
  );
}

function NotificationBell({ persona }: { persona: "investor" | "founder" }) {
  const navigate = useNavigate();
  const [items, setItems] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);

  async function refresh() {
    setItems(await listNotifications());
  }
  useEffect(() => { void refresh(); }, []);
  useEffect(() => { if (open) void refresh(); }, [open]);

  const unread = items.filter((n) => !n.read).length;

  async function onOpen(n: Notification) {
    if (!n.read) { await markNotificationRead(n.id); await refresh(); }
    if (n.founderId && persona === "investor") {
      setOpen(false);
      navigate({ to: "/founder/$id", params: { id: n.founderId } });
    }
  }

  async function respond(n: Notification, action: "accept" | "decline") {
    if (!n.invitationId) return;
    await respondToInvitation(n.invitationId, action);
    await markNotificationRead(n.id);
    await refresh();
    toast.success(action === "accept" ? "Invitation accepted." : "Invitation declined.");
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          {unread > 0 ? (
            <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-gradient-brand px-1 font-mono text-[10px] text-primary-foreground">
              {unread}
            </span>
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-96 p-0">
        <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
          <div className="font-display text-sm font-semibold">Notifications</div>
          <button
            onClick={async () => { await markAllNotificationsRead(); await refresh(); }}
            className="text-xs text-muted-foreground hover:text-brand"
          >
            Mark all as read
          </button>
        </div>
        <div className="max-h-96 overflow-y-auto">
          {items.length === 0 ? (
            <div className="p-6 text-center text-sm text-muted-foreground">Nothing here yet.</div>
          ) : (
            items.map((n) => (
              <div
                key={n.id}
                className={cn(
                  "border-b border-border/40 px-4 py-3 text-sm transition",
                  !n.read ? "bg-gradient-brand/5" : "",
                )}
              >
                <button className="w-full text-left" onClick={() => onOpen(n)}>
                  <div className="flex items-start gap-2">
                    {!n.read ? <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-brand" /> : <span className="mt-1.5 h-2 w-2 shrink-0" />}
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium">{n.title}</div>
                      <div className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{n.body}</div>
                    </div>
                  </div>
                </button>
                {n.kind === "invitation" && n.invitationId ? (
                  <div className="mt-2 flex gap-2 pl-4">
                    <Button size="sm" className="h-7 bg-gradient-brand text-primary-foreground" onClick={() => respond(n, "accept")}>Accept</Button>
                    <Button size="sm" variant="outline" className="h-7" onClick={() => respond(n, "decline")}>Decline</Button>
                  </div>
                ) : null}
              </div>
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
