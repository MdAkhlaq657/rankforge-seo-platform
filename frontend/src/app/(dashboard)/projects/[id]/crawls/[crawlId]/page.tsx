"use client";
import { use, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { crawlsApi } from "@/lib/api";
import { CrawlSummary, CrawledPage, AuditIssue } from "@/types";
import SeverityBadge from "@/components/ui/SeverityBadge";
import CWVIndicator from "@/components/ui/CWVIndicator";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

type Tab = "pages" | "issues";

export default function CrawlDetailPage({ params }: { params: { id: string, crawlId: string } }) {
  const { id, crawlId } = params;
  const [tab, setTab] = useState<Tab>("issues");
  const [severityFilter, setSeverityFilter] = useState<string>("all");

  const { data: summary } = useQuery<CrawlSummary>({
    queryKey: ["crawl-summary", id, crawlId],
    queryFn: async () => {
      const { data } = await crawlsApi.getSummary(id, crawlId);
      return data;
    },
  });

  const { data: pages = [] } = useQuery<CrawledPage[]>({
    queryKey: ["crawl-pages", crawlId],
    queryFn: async () => {
      const { data } = await crawlsApi.getPages(id, crawlId, { limit: 200 });
      return data;
    },
    enabled: tab === "pages",
  });

  const { data: issues = [] } = useQuery<AuditIssue[]>({
    queryKey: ["crawl-issues", crawlId, severityFilter],
    queryFn: async () => {
      const { data } = await crawlsApi.getIssues(id, crawlId, {
        severity: severityFilter === "all" ? undefined : severityFilter,
        limit: 500,
      });
      return data;
    },
    enabled: tab === "issues",
  });

  return (
    <div>
      <Link
        href={`/projects/${id}`}
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5"
      >
        <ArrowLeft size={14} /> Back to project
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Crawl report</h1>
          {summary && (
            <p className="text-sm text-gray-500 mt-0.5">
              {summary.crawl.pages_crawled} pages · {summary.crawl.issues_found} issues
            </p>
          )}
        </div>
        {summary && (
          <div className={`text-center px-5 py-2 rounded-xl border ${
            summary.score >= 80 ? "bg-green-50 border-green-200" :
            summary.score >= 50 ? "bg-amber-50 border-amber-200" : "bg-red-50 border-red-200"
          }`}>
            <p className={`text-3xl font-bold ${
              summary.score >= 80 ? "text-green-600" :
              summary.score >= 50 ? "text-amber-600" : "text-red-600"
            }`}>{summary.score}</p>
            <p className="text-xs text-gray-500 mt-0.5">Health score</p>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {(["issues", "pages"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium -mb-px border-b-2 transition-colors",
              tab === t
                ? "border-brand-600 text-brand-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            )}
          >
            {t === "issues" ? "Issues" : "All pages"}
          </button>
        ))}
      </div>

      {/* Issues tab */}
      {tab === "issues" && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            {["all", "p1", "p2", "p3"].map((s) => (
              <button
                key={s}
                onClick={() => setSeverityFilter(s)}
                className={cn(
                  "px-3 py-1 rounded-full text-xs font-medium border transition-colors",
                  severityFilter === s
                    ? "bg-brand-600 text-white border-brand-600"
                    : "bg-white text-gray-600 border-gray-200 hover:border-gray-300"
                )}
              >
                {s === "all" ? "All" : s.toUpperCase()}
              </button>
            ))}
            <span className="text-xs text-gray-400 ml-2">{issues.length} issues</span>
          </div>

          <div className="card divide-y divide-gray-50">
            {issues.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-gray-400">No issues found</p>
            ) : (
              issues.map((issue) => (
                <div key={issue.id} className="px-5 py-4 hover:bg-gray-50/60 transition-colors">
                  <div className="flex items-start gap-3">
                    <div className="pt-0.5">
                      <SeverityBadge severity={issue.severity} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 text-sm">{issue.title}</p>
                      <p className="text-xs text-gray-500 mt-0.5 truncate font-mono">
                        {issue.affected_url}
                      </p>
                      {issue.description && (
                        <p className="text-xs text-gray-400 mt-1.5 leading-relaxed">
                          {issue.description}
                        </p>
                      )}
                      {issue.recommendation && (
                        <p className="text-xs text-brand-600 mt-1">
                          ✦ {issue.recommendation}
                        </p>
                      )}
                    </div>
                    <a
                      href={issue.affected_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-gray-300 hover:text-brand-500 flex-shrink-0 mt-0.5"
                    >
                      <ExternalLink size={14} />
                    </a>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Pages tab */}
      {tab === "pages" && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {["URL", "Status", "Title", "H1", "Words", "CWV", "Issues"].map((h) => (
                  <th key={h} className="text-left px-4 py-3 text-xs text-gray-500 font-medium whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pages.map((page) => (
                <tr key={page.id} className="table-row">
                  <td className="px-4 py-3 max-w-xs">
                    <a
                      href={page.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-brand-600 hover:underline text-xs font-mono truncate block"
                    >
                      {page.url.replace(/^https?:\/\/[^/]+/, "") || "/"}
                    </a>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      "badge text-xs",
                      page.status_code === 200 ? "bg-green-100 text-green-700" :
                      (page.status_code ?? 0) >= 400 ? "bg-red-100 text-red-700" :
                      (page.status_code ?? 0) >= 300 ? "bg-amber-100 text-amber-700" :
                      "bg-gray-100 text-gray-600"
                    )}>
                      {page.status_code ?? "?"}
                    </span>
                  </td>
                  <td className="px-4 py-3 max-w-xs">
                    <span className={cn(
                      "text-xs truncate block",
                      !page.title ? "text-red-500 italic" : "text-gray-700"
                    )}>
                      {page.title ?? "Missing"}
                    </span>
                    {page.title_length != null && (
                      <span className={cn(
                        "text-xs",
                        page.title_length < 30 || page.title_length > 65
                          ? "text-amber-500"
                          : "text-gray-400"
                      )}>
                        {page.title_length} chars
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      "text-xs",
                      page.h1_count === 0 ? "text-red-500 italic" :
                      page.h1_count > 1 ? "text-amber-500" : "text-gray-700"
                    )}>
                      {page.h1_count === 0 ? "Missing" : `${page.h1_count} H1`}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {page.word_count.toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <CWVIndicator
                      lcp={page.lcp_mobile}
                      cls={page.cls_mobile}
                      inp={page.inp_mobile}
                    />
                  </td>
                  <td className="px-4 py-3">
                    {page.issues_count > 0 ? (
                      <span className="badge bg-red-100 text-red-700 text-xs">
                        {page.issues_count}
                      </span>
                    ) : (
                      <span className="text-green-500 text-xs">✓</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
