"use client";
import Link from "next/link";
import { usePathname, useParams, useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard, FolderOpen, Search, BarChart2, FileText,
  LogOut, Zap, TrendingUp, PenTool, PlugZap, FileBarChart,
  Target, Link2, Users, BrainCircuit, CreditCard,
} from "lucide-react";

const mainNav = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/projects",  icon: FolderOpen,      label: "Projects"  },
  { href: "/billing",   icon: CreditCard,      label: "Billing"   },
];

const projectNav = [
  { href: "",               icon: BarChart2,    label: "Overview"        },
  { href: "/crawls",        icon: Search,       label: "Crawls & Audit"  },
  { href: "/keywords",      icon: Target,       label: "Keywords"        },
  { href: "/rank-tracking", icon: TrendingUp,   label: "Rank Tracking"   },
  { href: "/on-page",       icon: FileText,     label: "On-Page NLP"     },
  { href: "/backlinks",     icon: Link2,        label: "Backlinks"       },
  { href: "/competitors",   icon: Users,        label: "Competitors"     },
  { href: "/link-building", icon: Link2,        label: "Link Building"   },
  { href: "/analytics",     icon: BrainCircuit, label: "Analytics"       },
  { href: "/content",       icon: PenTool,      label: "Content Writer"  },
  { href: "/tasks",         icon: FileText,     label: "Task Board"      },
  { href: "/integrations",  icon: PlugZap,      label: "Integrations"    },
  { href: "/reports",       icon: FileBarChart, label: "Reports"         },
];

export default function Sidebar() {
  const pathname = usePathname();
  const params = useParams();
    const router = useRouter();
  const { user, currentOrg, logout } = useAuthStore();
  const projectId = params?.id as string | undefined;

  return (
    <aside className="fixed top-0 left-0 h-screen w-60 bg-gray-950 flex flex-col z-40">
      <div className="px-5 py-4 border-b border-gray-800">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 bg-brand-500 rounded-md flex items-center justify-center flex-shrink-0">
            <Zap size={14} className="text-white" />
          </div>
          <span className="text-white font-semibold text-sm">RankForge</span>
        </div>
        {currentOrg && (
          <p className="text-gray-500 text-xs mt-1 truncate">{currentOrg.name}</p>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-0.5">
        {mainNav.map(({ href, icon: Icon, label }) => (
          <Link key={href} href={href}
            className={cn(
              "flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors",
              pathname === href ? "bg-brand-600 text-white" : "text-gray-400 hover:text-white hover:bg-gray-800"
            )}
          >
            <Icon size={15} />{label}
          </Link>
        ))}

        {projectId && (
          <div className="mt-3 pt-3 border-t border-gray-800">
            <p className="text-gray-600 text-xs font-medium uppercase tracking-wider px-3 mb-1.5">Project</p>
            {projectNav.map(({ href, icon: Icon, label }) => {
              const fullHref = `/projects/${projectId}${href}`;
              const isActive = href === "" ? pathname === fullHref : pathname.startsWith(fullHref);
              return (
                <Link key={href} href={fullHref}
                  className={cn(
                    "flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-sm transition-colors",
                    isActive ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white hover:bg-gray-800"
                  )}
                >
                  <Icon size={14} /><span className="truncate">{label}</span>
                </Link>
              );
            })}
          </div>
        )}
      </nav>

      <div className="px-3 py-3 border-t border-gray-800">
        <div className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg mb-1">
          <div className="w-7 h-7 rounded-full bg-brand-700 flex items-center justify-center flex-shrink-0">
            <span className="text-white text-xs font-medium">
              {user?.full_name?.[0] ?? user?.email?.[0]?.toUpperCase() ?? "U"}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-white text-xs font-medium truncate">{user?.full_name ?? "User"}</p>
            <p className="text-gray-500 text-xs truncate">{user?.email}</p>
          </div>
        </div>
        <button onClick ={() => {
          logout();
          router.push("/login")
        }}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-gray-800 transition-colors">
          <LogOut size={14} />Sign out
        </button>
      </div>
    </aside>
  );
}
