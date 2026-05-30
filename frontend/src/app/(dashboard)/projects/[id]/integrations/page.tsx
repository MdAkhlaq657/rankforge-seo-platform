"use client";
import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { integrationsApi } from "@/lib/api";
import { cn, formatRelative } from "@/lib/utils";
import { ArrowLeft, PlugZap, RefreshCw, Unplug, CheckCircle } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend,
} from "recharts";

type PerfPeriod = "30" | "60" | "90";

export default function IntegrationsPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const qc = useQueryClient();
  const [perfPeriod, setPerfPeriod] = useState<PerfPeriod>("30");
  const [connectingMock, setConnectingMock] = useState(false);

  const { data: integrations = [] } = useQuery<any[]>({
    queryKey: ["integrations", id],
    queryFn: async () => { const { data } = await integrationsApi.list(id); return data; },
  });

  const { data: performance = [] } = useQuery<any[]>({
    queryKey: ["gsc-performance", id, perfPeriod],
    queryFn: async () => {
      const { data } = await integrationsApi.gscPerformance(id, { days: Number(perfPeriod) });
      return data;
    },
  });

  const { data: topQueries = [] } = useQuery<any[]>({
    queryKey: ["gsc-top-queries", id],
    queryFn: async () => {
      const { data } = await integrationsApi.gscTopQueries(id, { days: 30, limit: 15 });
      return data;
    },
  });

  const connectMock = useMutation({
    mutationFn: () => integrationsApi.connectMock(id, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["integrations", id] });
      qc.invalidateQueries({ queryKey: ["gsc-performance", id] });
      toast.success("Google Search Console connected (mock data)");
    },
    onError: () => toast.error("Connection failed"),
  });

  const disconnect = useMutation({
    mutationFn: (iid: string) => integrationsApi.disconnect(id, iid),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["integrations", id] });
      toast.success("Disconnected");
    },
  });

  const syncNow = useMutation({
    mutationFn: (iid: string) => integrationsApi.sync(id, iid),
    onSuccess: () => toast.success("Sync queued"),
  });

  const gscIntegration = integrations.find((i: any) => i.provider === "gsc");
  const isConnected = !!gscIntegration;

  const chartData = performance.map((d: any) => ({
    date: d.date.slice(5), // MM-DD
    Clicks: d.clicks,
    Impressions: Math.round(d.impressions / 10), // scale down for dual axis
    Position: d.avg_position,
  })).slice(-Number(perfPeriod));

  return (
    <div>
      <Link href={`/projects/${id}`} className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5">
        <ArrowLeft size={14} /> Back to project
      </Link>

      <h1 className="text-xl font-semibold text-gray-900 mb-6">Integrations</h1>

      {/* GSC card */}
      <div className="card p-5 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={cn(
              "w-10 h-10 rounded-xl flex items-center justify-center",
              isConnected ? "bg-green-100" : "bg-gray-100"
            )}>
              {isConnected
                ? <CheckCircle size={20} className="text-green-600" />
                : <PlugZap size={20} className="text-gray-400" />
              }
            </div>
            <div>
              <p className="font-medium text-gray-900">Google Search Console</p>
              {isConnected ? (
                <p className="text-xs text-green-600 mt-0.5">
                  Connected · {gscIntegration.property_id} ·{" "}
                  Last synced {formatRelative(gscIntegration.last_synced_at)}
                </p>
              ) : (
                <p className="text-xs text-gray-400 mt-0.5">
                  Connect to see clicks, impressions, CTR, and rankings
                </p>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            {isConnected ? (
              <>
                <button
                  className="btn-secondary"
                  onClick={() => syncNow.mutate(gscIntegration.id)}
                  disabled={syncNow.isPending}
                >
                  <RefreshCw size={14} className={syncNow.isPending ? "animate-spin" : ""} />
                  Sync now
                </button>
                <button
                  className="btn-secondary text-red-500 hover:text-red-600"
                  onClick={() => disconnect.mutate(gscIntegration.id)}
                >
                  <Unplug size={14} /> Disconnect
                </button>
              </>
            ) : (
              <button
                className="btn-primary"
                onClick={() => connectMock.mutate()}
                disabled={connectMock.isPending}
              >
                <PlugZap size={14} />
                {connectMock.isPending ? "Connecting…" : "Connect GSC (mock)"}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Performance charts */}
      {performance.length > 0 && (
        <>
          {/* Period selector */}
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-gray-700">Search performance</h2>
            <div className="flex gap-1">
              {(["30", "60", "90"] as PerfPeriod[]).map(p => (
                <button
                  key={p}
                  onClick={() => setPerfPeriod(p)}
                  className={cn(
                    "px-3 py-1 rounded-full text-xs font-medium border transition-colors",
                    perfPeriod === p
                      ? "bg-brand-600 text-white border-brand-600"
                      : "bg-white text-gray-600 border-gray-200 hover:border-gray-300"
                  )}
                >{p}d</button>
              ))}
            </div>
          </div>

          {/* Clicks + Impressions chart */}
          <div className="card p-5 mb-4">
            <h3 className="text-xs font-medium text-gray-500 mb-3 uppercase tracking-wide">
              Clicks &amp; Impressions (÷10)
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e5e7eb" }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="Clicks" stroke="#6366f1" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="Impressions" stroke="#94a3b8" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Position chart */}
          <div className="card p-5 mb-6">
            <h3 className="text-xs font-medium text-gray-500 mb-3 uppercase tracking-wide">
              Average position (lower = better)
            </h3>
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                <YAxis reversed tick={{ fontSize: 11 }} domain={["auto", "auto"]} />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e5e7eb" }}
                  formatter={(v: any) => [`#${v}`, "Avg position"]}
                />
                <Line type="monotone" dataKey="Position" stroke="#f59e0b" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Top queries */}
          {topQueries.length > 0 && (
            <div className="card">
              <div className="px-5 py-3 border-b border-gray-100">
                <h3 className="text-sm font-medium text-gray-700">Top queries (last 30 days)</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100">
                      {["Query", "Clicks", "Impressions", "CTR", "Avg position"].map(h => (
                        <th key={h} className="text-left px-4 py-2.5 text-xs text-gray-500 font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {topQueries.map((q: any, i: number) => (
                      <tr key={i} className="border-b border-gray-50 hover:bg-gray-50/60 transition-colors">
                        <td className="px-4 py-2.5 font-medium text-gray-900">{q.query}</td>
                        <td className="px-4 py-2.5 text-brand-600 font-semibold">{q.clicks.toLocaleString()}</td>
                        <td className="px-4 py-2.5 text-gray-600">{q.impressions.toLocaleString()}</td>
                        <td className="px-4 py-2.5 text-gray-600">{q.ctr}%</td>
                        <td className="px-4 py-2.5 text-gray-600">#{q.position}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {!isConnected && performance.length === 0 && (
        <div className="card p-12 text-center text-sm text-gray-400">
          Connect Google Search Console to see performance data
        </div>
      )}
    </div>
  );
}
