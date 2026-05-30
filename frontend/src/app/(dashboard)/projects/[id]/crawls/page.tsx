"use client";
import { use } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { crawlsApi } from "@/lib/api";
import { Crawl } from "@/types";
import { crawlStatusBadge, formatDate, formatRelative } from "@/lib/utils";
import { Play, RefreshCw, ArrowLeft, ArrowRight } from "lucide-react";

export default function CrawlPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const qc = useQueryClient();

  const { data: crawls = [], isLoading } = useQuery<Crawl[]>({
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

  const startCrawl = useMutation({
    mutationFn: () => crawlsApi.start(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["crawls", id] });
      toast.success("Crawl started!");
    },
    onError: (err: any) =>
      toast.error(err.response?.data?.detail ?? "Failed to start crawl"),
  });

  const isRunning = crawls.some(
    (c) => c.status === "running" || c.status === "pending",
  );

  return (
    <div>
      <Link
        href={`/projects/${id}`}
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5"
      >
        <ArrowLeft size={14} /> Back to project
      </Link>

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-gray-900">Crawl history</h1>
        <button
          className="btn-primary"
          onClick={() => startCrawl.mutate()}
          disabled={isRunning || startCrawl.isPending}
        >
          {isRunning ? (
            <>
              <RefreshCw size={15} className="animate-spin" /> Running…
            </>
          ) : (
            <>
              <Play size={15} /> New crawl
            </>
          )}
        </button>
      </div>

      <div className="card divide-y divide-gray-50">
        {isLoading ? (
          <p className="px-5 py-8 text-center text-sm text-gray-400">
            Loading…
          </p>
        ) : crawls.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-gray-400">
            No crawls yet
          </p>
        ) : (
          crawls.map((crawl) => (
            <div key={crawl.id} className="px-5 py-4 flex items-center gap-4">
              <span className={`badge ${crawlStatusBadge(crawl.status)}`}>
                {crawl.status}
              </span>
              <div className="flex-1">
                <p className="text-sm text-gray-700">
                  {crawl.pages_crawled} pages ·{" "}
                  <span
                    className={
                      crawl.issues_found > 0
                        ? "text-amber-600"
                        : "text-green-600"
                    }
                  >
                    {crawl.issues_found} issues
                  </span>
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {formatDate(crawl.created_at)} ·{" "}
                  {formatRelative(crawl.created_at)}
                </p>
              </div>
              {crawl.status === "completed" && (
                <Link
                  href={`/projects/${id}/crawls/${crawl.id}`}
                  className="text-xs text-brand-600 hover:underline flex items-center gap-1"
                >
                  View report <ArrowRight size={11} />
                </Link>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
