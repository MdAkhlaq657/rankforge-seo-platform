"use client";
import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { rankApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ArrowLeft, RefreshCw, TrendingUp, TrendingDown, Minus } from "lucide-react";
import {
  LineChart, Line, ResponsiveContainer, Tooltip,
  BarChart, Bar, Cell, XAxis, YAxis,
} from "recharts";

function Sparkline({ data }: { data: (number | null)[] }) {
  if (!data || data.length < 2) return <span className="text-gray-300 text-xs">—</span>;
  const filtered = data.filter(Boolean) as number[];
  if (!filtered.length) return <span className="text-gray-300 text-xs">—</span>;
  const chartData = data.map((v, i) => ({ i, v: v ?? null }));
  return (
    <ResponsiveContainer width={80} height={28}>
      <LineChart data={chartData}>
        <Line
          type="monotone"
          dataKey="v"
          stroke="#6366f1"
          strokeWidth={1.5}
          dot={false}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function DeltaBadge({ delta }: { delta: number | null }) {
  if (delta === null || delta === undefined)
    return <span className="text-gray-300 text-xs">—</span>;
  if (delta > 0)
    return <span className="text-green-600 text-xs font-medium flex items-center gap-0.5"><TrendingUp size={12} />+{delta}</span>;
  if (delta < 0)
    return <span className="text-red-500 text-xs font-medium flex items-center gap-0.5"><TrendingDown size={12} />{delta}</span>;
  return <span className="text-gray-400 text-xs flex items-center gap-0.5"><Minus size={12} />0</span>;
}

const BUCKET_LABELS: Record<string, string> = {
  top_3: "Top 3", "4_10": "4–10", "11_20": "11–20",
  "21_50": "21–50", "51_100": "51–100", not_ranking: "Not ranking",
};
const BUCKET_COLORS: Record<string, string> = {
  top_3: "#22c55e", "4_10": "#6366f1", "11_20": "#f59e0b",
  "21_50": "#94a3b8", "51_100": "#d1d5db", not_ranking: "#f3f4f6",
};

export default function RankTrackingPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [intentFilter, setIntentFilter] = useState("all");

  const { data: rankings = [], isLoading, refetch } = useQuery<any[]>({
    queryKey: ["ranks", id],
    queryFn: async () => { const { data } = await rankApi.summary(id); return data; },
    refetchInterval: false,
  });

  const { data: stats } = useQuery<any>({
    queryKey: ["rank-stats", id],
    queryFn: async () => { const { data } = await rankApi.stats(id); return data; },
  });

  const checkNow = useMutation({
    mutationFn: () => rankApi.checkNow(id),
    onSuccess: () => {
      toast.success("Rank check queued — results in ~1 minute");
      setTimeout(() => refetch(), 60000);
    },
    onError: () => toast.error("Failed to trigger check"),
  });

  const filtered = intentFilter === "all"
    ? rankings
    : rankings.filter((r: any) => r.intent === intentFilter);

  const bucketData = stats?.buckets
    ? Object.entries(stats.buckets).map(([k, v]) => ({
        name: BUCKET_LABELS[k] ?? k,
        value: v as number,
        key: k,
      }))
    : [];

  return (
    <div>
      <Link href={`/projects/${id}`} className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5">
        <ArrowLeft size={14} /> Back to project
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Rank Tracking</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {stats?.total_tracked ?? 0} tracked keywords
          </p>
        </div>
        <button
          className="btn-primary"
          onClick={() => checkNow.mutate()}
          disabled={checkNow.isPending}
        >
          <RefreshCw size={15} className={checkNow.isPending ? "animate-spin" : ""} />
          Check ranks now
        </button>
      </div>

      {/* Distribution chart */}
      {bucketData.length > 0 && (
        <div className="card p-5 mb-6">
          <h2 className="text-sm font-medium text-gray-700 mb-4">Position distribution</h2>
          <div className="flex items-end gap-6">
            <ResponsiveContainer width="60%" height={80}>
              <BarChart data={bucketData} barSize={28}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis hide />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e5e7eb" }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {bucketData.map(b => (
                    <Cell key={b.key} fill={BUCKET_COLORS[b.key] ?? "#6366f1"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div className="grid grid-cols-3 gap-x-6 gap-y-2">
              {bucketData.map(b => (
                <div key={b.key} className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-sm flex-shrink-0" style={{ background: BUCKET_COLORS[b.key] }} />
                  <span className="text-xs text-gray-500">{b.name}</span>
                  <span className="text-xs font-semibold text-gray-700">{b.value as number}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Intent filter */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {["all", "informational", "commercial", "transactional", "navigational"].map(i => (
          <button
            key={i}
            onClick={() => setIntentFilter(i)}
            className={cn(
              "px-3 py-1 rounded-full text-xs font-medium border transition-colors capitalize",
              intentFilter === i
                ? "bg-brand-600 text-white border-brand-600"
                : "bg-white text-gray-600 border-gray-200 hover:border-gray-300"
            )}
          >{i}</button>
        ))}
      </div>

      {/* Rankings table */}
      {isLoading ? (
        <div className="card p-8 text-center text-sm text-gray-400">Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="card p-10 text-center text-sm text-gray-400">
          No tracked keywords yet. Add keywords in the Keywords tab.
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                {["Keyword", "Position", "Δ 7d", "Volume", "Intent", "SERP features", "Trend (30d)", "URL"].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs text-gray-500 font-medium whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((r: any) => (
                <tr key={r.keyword_id} className="border-b border-gray-50 hover:bg-gray-50/60 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900 max-w-xs">
                    <span className="truncate block">{r.keyword}</span>
                  </td>
                  <td className="px-4 py-3">
                    {r.current_position != null ? (
                      <span className={cn(
                        "text-lg font-bold",
                        r.current_position <= 3 ? "text-green-600" :
                        r.current_position <= 10 ? "text-brand-600" :
                        r.current_position <= 20 ? "text-amber-600" : "text-gray-500"
                      )}>
                        #{r.current_position}
                      </span>
                    ) : (
                      <span className="text-gray-300 text-xs">Not ranking</span>
                    )}
                  </td>
                  <td className="px-4 py-3"><DeltaBadge delta={r.delta} /></td>
                  <td className="px-4 py-3 text-gray-600 text-xs">
                    {r.search_volume != null ? r.search_volume.toLocaleString() : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span className="badge bg-gray-100 text-gray-600 text-xs">{r.intent}</span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {r.serp_features?.slice(0, 2).map((f: string) => (
                        <span key={f} className="badge bg-purple-100 text-purple-700 text-xs">
                          {f.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Sparkline data={r.sparkline ?? []} />
                  </td>
                  <td className="px-4 py-3 max-w-xs">
                    {r.best_url ? (
                      <a
                        href={r.best_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-brand-600 hover:underline text-xs font-mono truncate block"
                      >
                        {r.best_url.replace(/^https?:\/\/[^/]+/, "") || "/"}
                      </a>
                    ) : <span className="text-gray-300 text-xs">—</span>}
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
