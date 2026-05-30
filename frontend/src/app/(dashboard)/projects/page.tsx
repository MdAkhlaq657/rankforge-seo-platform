"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import { Project } from "@/types";
import { crawlStatusBadge, formatRelative } from "@/lib/utils";
import { Plus, Globe, ArrowRight } from "lucide-react";

export default function ProjectsPage() {
  const { data: projects = [], isLoading } = useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: async () => {
      const { data } = await projectsApi.list();
      return data;
    },
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Projects</h1>
        <Link href="/projects/new" className="btn-primary">
          <Plus size={16} /> New project
        </Link>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="card p-5 animate-pulse h-36 bg-gray-50" />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <div className="card p-12 text-center">
          <Globe size={40} className="mx-auto text-gray-200 mb-3" />
          <p className="font-medium text-gray-600">No projects yet</p>
          <p className="text-sm text-gray-400 mt-1 mb-4">Add your first website to begin SEO auditing</p>
          <Link href="/projects/new" className="btn-primary inline-flex">
            <Plus size={15} /> Create first project
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p) => (
            <Link key={p.id} href={`/projects/${p.id}`} className="card p-5 hover:shadow-md transition-shadow block group">
              <div className="flex items-start justify-between mb-3">
                <div className="w-9 h-9 rounded-lg bg-brand-50 flex items-center justify-center flex-shrink-0">
                  <Globe size={18} className="text-brand-600" />
                </div>
                {p.last_crawl_status && (
                  <span className={`badge ${crawlStatusBadge(p.last_crawl_status as any)}`}>
                    {p.last_crawl_status}
                  </span>
                )}
              </div>
              <h3 className="font-semibold text-gray-900 group-hover:text-brand-600 transition-colors">
                {p.name}
              </h3>
              <p className="text-xs text-gray-500 font-mono mt-0.5">{p.domain}</p>
              <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-50">
                <div className="flex gap-4">
                  <span className="text-xs text-gray-500">
                    <span className="font-medium text-gray-700">{p.total_pages ?? "—"}</span> pages
                  </span>
                  <span className="text-xs text-gray-500">
                    <span className={`font-medium ${p.open_issues ? "text-amber-600" : "text-gray-700"}`}>
                      {p.open_issues ?? "—"}
                    </span>{" "}
                    issues
                  </span>
                </div>
                <span className="text-xs text-gray-400">{formatRelative(p.last_crawl_at)}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
