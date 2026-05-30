"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { Project } from "@/types";
import StatCard from "@/components/ui/StatCard";
import { crawlStatusBadge, formatRelative } from "@/lib/utils";
import { Plus, Globe, AlertCircle, CheckCircle, Clock, ArrowRight } from "lucide-react";

export default function DashboardPage() {
  const { user, currentOrg } = useAuthStore();

  const { data: projects = [], isLoading } = useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: async () => {
      const { data } = await projectsApi.list();
      return data;
    },
  });

  const totalIssues = projects.reduce((s, p) => s + (p.open_issues ?? 0), 0);
  const activeProjects = projects.filter((p) => p.last_crawl_status === "completed").length;
  const runningCrawls = projects.filter((p) => p.last_crawl_status === "running").length;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">
            Good morning{user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {currentOrg?.name} · {currentOrg?.plan} plan
          </p>
        </div>
        <Link href="/projects/new" className="btn-primary">
          <Plus size={16} />
          New project
        </Link>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total projects" value={projects.length} icon={<Globe size={18} />} />
        <StatCard label="Open issues" value={totalIssues} color={totalIssues > 0 ? "amber" : "green"} icon={<AlertCircle size={18} />} />
        <StatCard label="Crawls complete" value={activeProjects} color="green" icon={<CheckCircle size={18} />} />
        <StatCard label="Crawls running" value={runningCrawls} color={runningCrawls > 0 ? "blue" : "default"} icon={<Clock size={18} />} />
      </div>

      {/* Credits */}
      <div className="card p-5 mb-8">
        <h2 className="text-sm font-medium text-gray-700 mb-3">Monthly credits</h2>
        <div className="grid grid-cols-2 gap-6">
          <div>
            <div className="flex justify-between text-xs mb-1.5">
              <span className="text-gray-500">Crawl credits</span>
              <span className="font-medium text-gray-700">
                {(currentOrg?.crawl_credits ?? 0).toLocaleString()} remaining
              </span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-500 rounded-full transition-all"
                style={{ width: `${Math.min(100, ((currentOrg?.crawl_credits ?? 0) / 5000) * 100)}%` }}
              />
            </div>
          </div>
          <div>
            <div className="flex justify-between text-xs mb-1.5">
              <span className="text-gray-500">Keyword credits</span>
              <span className="font-medium text-gray-700">
                {(currentOrg?.keyword_credits ?? 0).toLocaleString()} remaining
              </span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-500 rounded-full transition-all"
                style={{ width: `${Math.min(100, ((currentOrg?.keyword_credits ?? 0) / 500) * 100)}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Projects table */}
      <div className="card">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="font-medium text-gray-900">Projects</h2>
          <Link href="/projects" className="text-xs text-brand-600 hover:underline flex items-center gap-1">
            View all <ArrowRight size={12} />
          </Link>
        </div>

        {isLoading ? (
          <div className="px-6 py-12 text-center text-sm text-gray-400">Loading projects…</div>
        ) : projects.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <Globe size={32} className="mx-auto text-gray-200 mb-3" />
            <p className="text-sm font-medium text-gray-600">No projects yet</p>
            <p className="text-xs text-gray-400 mb-4">Add your first website to start crawling</p>
            <Link href="/projects/new" className="btn-primary inline-flex">
              <Plus size={15} /> Create project
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-6 py-3 text-xs text-gray-500 font-medium">Project</th>
                  <th className="text-left px-4 py-3 text-xs text-gray-500 font-medium">Domain</th>
                  <th className="text-left px-4 py-3 text-xs text-gray-500 font-medium">Last crawl</th>
                  <th className="text-left px-4 py-3 text-xs text-gray-500 font-medium">Pages</th>
                  <th className="text-left px-4 py-3 text-xs text-gray-500 font-medium">Open issues</th>
                  <th className="text-left px-4 py-3 text-xs text-gray-500 font-medium">Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {projects.map((p) => (
                  <tr key={p.id} className="table-row">
                    <td className="px-6 py-3 font-medium text-gray-900">{p.name}</td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{p.domain}</td>
                    <td className="px-4 py-3 text-gray-500">{formatRelative(p.last_crawl_at)}</td>
                    <td className="px-4 py-3 text-gray-700">{p.total_pages ?? "—"}</td>
                    <td className="px-4 py-3">
                      {p.open_issues != null && p.open_issues > 0 ? (
                        <span className="text-amber-600 font-medium">{p.open_issues}</span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {p.last_crawl_status ? (
                        <span className={`badge ${crawlStatusBadge(p.last_crawl_status as any)}`}>
                          {p.last_crawl_status}
                        </span>
                      ) : (
                        <span className="text-gray-400 text-xs">Never crawled</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/projects/${p.id}`}
                        className="text-brand-600 text-xs hover:underline flex items-center gap-1"
                      >
                        Open <ArrowRight size={11} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
