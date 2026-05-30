"use client";
import { use } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { projectsApi, crawlsApi } from "@/lib/api";
import { Project, Crawl, CrawlSummary } from "@/types";
import StatCard from "@/components/ui/StatCard";
import CWVIndicator from "@/components/ui/CWVIndicator";
import { crawlStatusBadge, formatRelative, formatDate } from "@/lib/utils";
import {
  Play, RefreshCw, FileText, Search, ArrowRight,
  AlertTriangle, CheckCircle, Globe, BarChart2,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";

const ISSUE_COLORS: Record<string, string> = {
  missing_title: "#ef4444",
  duplicate_title: "#f97316",
  missing_meta: "#eab308",
  missing_h1: "#f97316",
  multiple_h1: "#eab308",
  broken_link: "#dc2626",
  noindex_key_page: "#dc2626",
  thin_content: "#6366f1",
  missing_canonical: "#8b5cf6",
  slow_cwv: "#06b6d4",
};

export default function ProjectPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const qc = useQueryClient();

  const { data: project } = useQuery<Project>({
    queryKey: ["project", id],
    queryFn: async () => {
      const { data } = await projectsApi.get(id);
      return data;
    },
  });

  const { data: crawls = [] } = useQuery<Crawl[]>({
    queryKey: ["crawls", id],
    queryFn: async () => {
      const { data } = await crawlsApi.list(id);
      return data;
    },
    refetchInterval: (query) => {
      const c = query.state.data as Crawl[] | undefined;
      return c?.some((cr) => cr.status === "running" || cr.status === "pending")
        ? 3000
        : false;
    },
  });

  const latestCrawl = crawls[0];

  const { data: summary } = useQuery<CrawlSummary>({
    queryKey: ["crawl-summary", id, latestCrawl?.id],
    queryFn: async () => {
      const { data } = await crawlsApi.getSummary(id, latestCrawl!.id);
      return data;
    },
    enabled: !!latestCrawl && latestCrawl.status === "completed",
  });

  const startCrawl = useMutation({
    mutationFn: () => crawlsApi.start(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["crawls", id] });
      toast.success("Crawl started!");
    },
    onError: (err: any) =>
      toast.error(err.response?.data?.detail ?? "Failed to start crawl"),
  });

  const isRunning =
    latestCrawl?.status === "running" || latestCrawl?.status === "pending";

  const issueChartData = summary
    ? Object.entries(summary.issue_breakdown)
        .map(([type, count]) => ({
          name: type.replace(/_/g, " "),
          count,
          type,
        }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 8)
    : [];

  const statusChartData = summary
    ? Object.entries(summary.status_code_breakdown).map(([code, count]) => ({
        code,
        count,
      }))
    : [];

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <p className="text-xs text-gray-400 mb-0.5">
            <Link href="/projects" className="hover:underline">
              Projects
            </Link>{" "}
            /
          </p>
          <h1 className="text-2xl font-semibold text-gray-900">
            {project?.name}
          </h1>
          <p className="text-sm text-gray-500 font-mono mt-0.5">
            {project?.domain}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href={`/projects/${id}/tasks`} className="btn-secondary">
            <FileText size={15} /> Task board
          </Link>
          <Link href={`/projects/${id}/crawls`} className="btn-secondary">
            <Search size={15} /> All crawls
          </Link>
          <button
            className="btn-primary"
            onClick={() => startCrawl.mutate()}
            disabled={isRunning || startCrawl.isPending}
          >
            {isRunning ? (
              <>
                <RefreshCw size={15} className="animate-spin" /> Crawling…
              </>
            ) : (
              <>
                <Play size={15} /> Start crawl
              </>
            )}
          </button>
        </div>
      </div>

      {/* Crawl status bar */}
      {isRunning && (
        <div className="mb-6 bg-blue-50 border border-blue-200 rounded-xl px-5 py-3 flex items-center gap-3">
          <RefreshCw size={16} className="text-blue-600 animate-spin" />
          <span className="text-sm text-blue-700 font-medium">
            Crawl in progress
          </span>
          <span className="text-sm text-blue-500">
            {latestCrawl?.pages_crawled ?? 0} pages crawled so far…
          </span>
        </div>
      )}

      {/* No crawl yet */}
      {!latestCrawl && !isRunning && (
        <div className="card p-12 text-center mb-6">
          <Globe size={36} className="mx-auto text-gray-200 mb-3" />
          <p className="font-medium text-gray-600">No crawls yet</p>
          <p className="text-sm text-gray-400 mt-1 mb-4">
            Start your first crawl to discover technical SEO issues
          </p>
          <button
            className="btn-primary inline-flex"
            onClick={() => startCrawl.mutate()}
          >
            <Play size={15} /> Start first crawl
          </button>
        </div>
      )}

      {summary && (
        <>
          {/* Score + stats */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
            <div className="card p-5 flex flex-col items-center justify-center lg:col-span-1">
              <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider font-medium">
                Health score
              </p>
              <div
                className={`text-5xl font-bold ${
                  summary.score >= 80
                    ? "text-green-500"
                    : summary.score >= 50
                      ? "text-amber-500"
                      : "text-red-500"
                }`}
              >
                {summary.score}
              </div>
              <p className="text-xs text-gray-400 mt-1">out of 100</p>
            </div>
            <StatCard
              label="Pages crawled"
              value={summary.crawl.pages_crawled}
              icon={<Globe size={17} />}
            />
            <StatCard
              label="Total issues"
              value={summary.crawl.issues_found}
              color={summary.crawl.issues_found > 0 ? "amber" : "green"}
              icon={<AlertTriangle size={17} />}
            />
            <StatCard
              label="Avg. Perf. score"
              value={summary.cwv_summary.avg_score}
              color={
                summary.cwv_summary.avg_score >= 80
                  ? "green"
                  : summary.cwv_summary.avg_score >= 50
                    ? "amber"
                    : "red"
              }
              sub="out of 100"
            />
            <StatCard
              label="Completed"
              value={formatDate(summary.crawl.completed_at)}
              sub={formatRelative(summary.crawl.completed_at)}
            />
          </div>

          {/* CWV summary */}
          <div className="card p-5 mb-6">
            <h2 className="text-sm font-medium text-gray-700 mb-3">
              Average Core Web Vitals (mobile)
            </h2>
            <CWVIndicator
              lcp={summary.cwv_summary.avg_lcp}
              cls={summary.cwv_summary.avg_cls}
              inp={summary.cwv_summary.avg_inp}
            />
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
            {/* Issues by type */}
            <div className="card p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-medium text-gray-700">
                  Issues by type
                </h2>
                <Link
                  href={`/projects/${id}/crawls/${latestCrawl?.id}`}
                  className="text-xs text-brand-600 hover:underline flex items-center gap-1"
                >
                  See all <ArrowRight size={11} />
                </Link>
              </div>
              {issueChartData.length === 0 ? (
                <div className="h-40 flex items-center justify-center">
                  <div className="text-center">
                    <CheckCircle
                      size={28}
                      className="mx-auto text-green-400 mb-2"
                    />
                    <p className="text-sm text-gray-400">No issues found</p>
                  </div>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart
                    data={issueChartData}
                    layout="vertical"
                    margin={{ left: 0, right: 16 }}
                  >
                    <XAxis type="number" tick={{ fontSize: 11 }} />
                    <YAxis
                      dataKey="name"
                      type="category"
                      width={120}
                      tick={{ fontSize: 11 }}
                    />
                    <Tooltip
                      contentStyle={{
                        fontSize: 12,
                        borderRadius: 8,
                        border: "1px solid #e5e7eb",
                      }}
                    />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                      {issueChartData.map((entry) => (
                        <Cell
                          key={entry.type}
                          fill={ISSUE_COLORS[entry.type] ?? "#6366f1"}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            {/* Status codes */}
            <div className="card p-5">
              <h2 className="text-sm font-medium text-gray-700 mb-4">
                Status code breakdown
              </h2>
              {statusChartData.length === 0 ? (
                <div className="h-40 flex items-center justify-center text-sm text-gray-400">
                  No data
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={statusChartData}>
                    <XAxis dataKey="code" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        fontSize: 12,
                        borderRadius: 8,
                        border: "1px solid #e5e7eb",
                      }}
                    />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {statusChartData.map((entry) => (
                        <Cell
                          key={entry.code}
                          fill={
                            entry.code === "2xx"
                              ? "#22c55e"
                              : entry.code === "3xx"
                                ? "#f59e0b"
                                : entry.code === "4xx"
                                  ? "#ef4444"
                                  : entry.code === "5xx"
                                    ? "#dc2626"
                                    : "#6366f1"
                          }
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Quick actions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Link
              href={`/projects/${id}/crawls/${latestCrawl?.id}`}
              className="card p-5 hover:shadow-md transition-shadow group flex items-center justify-between"
            >
              <div>
                <p className="font-medium text-gray-900 group-hover:text-brand-600">
                  View crawl report
                </p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {summary.crawl.issues_found} issues across{" "}
                  {summary.crawl.pages_crawled} pages
                </p>
              </div>
              <ArrowRight
                size={18}
                className="text-gray-300 group-hover:text-brand-500"
              />
            </Link>
            <Link
              href={`/projects/${id}/tasks`}
              className="card p-5 hover:shadow-md transition-shadow group flex items-center justify-between"
            >
              <div>
                <p className="font-medium text-gray-900 group-hover:text-brand-600">
                  Open task board
                </p>
                <p className="text-xs text-gray-500 mt-0.5">
                  Assign and track fixes for your team
                </p>
              </div>
              <ArrowRight
                size={18}
                className="text-gray-300 group-hover:text-brand-500"
              />
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
