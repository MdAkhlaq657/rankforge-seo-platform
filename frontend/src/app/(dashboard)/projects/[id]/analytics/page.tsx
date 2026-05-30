"use client";
import { use, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ArrowLeft, BrainCircuit, TrendingUp, TrendingDown, Minus, AlertTriangle } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine, BarChart, Bar, Cell,
} from "recharts";

type Tab = "cannibalization" | "roi" | "traffic";

const SEVERITY_STYLE: Record<string, string> = {
  high: "bg-red-100 text-red-700 border border-red-200",
  medium: "bg-amber-100 text-amber-700 border border-amber-200",
  low: "bg-blue-100 text-blue-700 border border-blue-200",
};

const REC_LABELS: Record<string, string> = {
  consolidate: "Merge pages into one comprehensive resource",
  canonicalize: "Add canonical tag pointing to preferred URL",
  differentiate: "Rewrite pages to target different search intent",
};

export default function AnalyticsPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [tab, setTab] = useState<Tab>("cannibalization");
  const [convRate, setConvRate] = useState("2");
  const [orderValue, setOrderValue] = useState("50");

  const { data: cannibalization, isLoading: cannLoading } = useQuery<any>({
    queryKey: ["cannibalization", id],
    queryFn: async () => { const { data } = await analyticsApi.cannibalization(id); return data; },
    enabled: tab === "cannibalization",
  });

  const { data: roi, isLoading: roiLoading } = useQuery<any>({
    queryKey: ["roi", id, convRate, orderValue],
    queryFn: async () => {
      const { data } = await analyticsApi.roiForecast(id, {
        conversion_rate: Number(convRate) / 100,
        order_value: Number(orderValue),
      });
      return data;
    },
    enabled: tab === "roi",
  });

  const { data: traffic, isLoading: traffLoading } = useQuery<any>({
    queryKey: ["traffic-forecast", id],
    queryFn: async () => { const { data } = await analyticsApi.trafficForecast(id, { forecast_days: 90 }); return data; },
    enabled: tab === "traffic",
  });

  const TABS = [
    { id: "cannibalization", label: "Cannibalization" },
    { id: "roi", label: "ROI Forecast" },
    { id: "traffic", label: "Traffic Forecast" },
  ] as const;

  // Traffic chart data
  const chartData = traffic ? [
    ...((traffic.historical ?? []).slice(-60).map((d: any) => ({ ...d, type: "historical" }))),
    ...((traffic.forecast ?? []).slice(0, 90).map((d: any) => ({ ...d, type: "forecast" }))),
  ] : [];

  const lastHistoricalDate = traffic?.historical?.slice(-1)[0]?.date;

  return (
    <div>
      <Link href={`/projects/${id}`} className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5">
        <ArrowLeft size={14} /> Back to project
      </Link>

      <div className="flex items-center gap-3 mb-6">
        <BrainCircuit size={22} className="text-brand-500" />
        <h1 className="text-xl font-semibold text-gray-900">Predictive Analytics</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 mb-6">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={cn("px-4 py-2.5 text-sm font-medium -mb-px border-b-2 transition-colors",
              tab === t.id ? "border-brand-600 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700"
            )}>{t.label}</button>
        ))}
      </div>

      {/* ── CANNIBALIZATION ── */}
      {tab === "cannibalization" && (
        <div>
          {cannLoading ? (
            <div className="card p-8 text-center text-sm text-gray-400">Analyzing…</div>
          ) : !cannibalization || cannibalization.total_issues === 0 ? (
            <div className="card p-10 text-center">
              <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <BrainCircuit size={22} className="text-green-600" />
              </div>
              <p className="font-medium text-gray-700">No cannibalization detected</p>
              <p className="text-sm text-gray-400 mt-1">
                Add more keywords and run rank checks to enable this analysis
              </p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="card px-5 py-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Total issues</p>
                  <p className="text-3xl font-bold text-red-600 mt-1">{cannibalization.total_issues}</p>
                </div>
                <div className="card px-5 py-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">High severity</p>
                  <p className="text-3xl font-bold text-red-600 mt-1">{cannibalization.high_severity}</p>
                </div>
                <div className="card px-5 py-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Action required</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {cannibalization.issues?.length ?? 0}
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                {cannibalization.issues?.map((issue: any, i: number) => (
                  <div key={i} className="card p-5">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <AlertTriangle size={15} className="text-amber-500" />
                          <p className="font-medium text-gray-900">"{issue.keyword}"</p>
                          <span className={`badge text-xs ${SEVERITY_STYLE[issue.severity]}`}>{issue.severity}</span>
                        </div>
                        <p className="text-xs text-gray-500">{issue.affected_keywords} competing keyword(s)</p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-gray-500 mb-1">Recommendation</p>
                        <span className="badge bg-brand-100 text-brand-700 border border-brand-200 text-xs capitalize">
                          {issue.recommendation}
                        </span>
                      </div>
                    </div>
                    <p className="text-xs text-gray-500 mb-3">{REC_LABELS[issue.recommendation]}</p>
                    <div className="space-y-1.5">
                      {issue.competing_urls?.map((u: any, j: number) => (
                        <div key={j} className="flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-2">
                          <span className={cn("text-xs font-bold w-5", j === 0 ? "text-green-600" : "text-gray-400")}>
                            #{j + 1}
                          </span>
                          <a href={u.url} target="_blank" rel="noopener noreferrer"
                            className="text-xs font-mono text-brand-600 hover:underline truncate flex-1">
                            {u.url}
                          </a>
                          <span className="text-xs text-gray-400">pos ~{Math.round(u.avg_position)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── ROI FORECAST ── */}
      {tab === "roi" && (
        <div>
          <div className="card p-5 mb-6">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Assumptions</h3>
            <div className="grid grid-cols-2 gap-4 max-w-sm">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Conversion rate (%)</label>
                <input type="number" className="input" value={convRate} onChange={e => setConvRate(e.target.value)}
                  min="0.1" max="100" step="0.1" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Avg. order value ($)</label>
                <input type="number" className="input" value={orderValue} onChange={e => setOrderValue(e.target.value)}
                  min="1" step="1" />
              </div>
            </div>
          </div>

          {roiLoading ? (
            <div className="card p-8 text-center text-sm text-gray-400">Calculating…</div>
          ) : roi ? (
            <>
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="card px-5 py-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Total opportunity</p>
                  <p className="text-3xl font-bold text-green-600 mt-1">${roi.total_opportunity_value?.toLocaleString()}</p>
                  <p className="text-xs text-gray-400 mt-0.5">monthly revenue uplift</p>
                </div>
                <div className="card px-5 py-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Keywords analyzed</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">{roi.keywords?.length ?? 0}</p>
                </div>
                <div className="card px-5 py-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Conversion rate</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">{convRate}%</p>
                </div>
              </div>

              <div className="card overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 bg-gray-50">
                      {["Keyword", "Volume", "Current pos.", "Opp. value", "Top-1 clicks/mo", "Top-1 revenue/mo"].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs text-gray-500 font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {roi.keywords?.slice(0, 25).map((kw: any, i: number) => (
                      <tr key={i} className="border-b border-gray-50 hover:bg-gray-50/60">
                        <td className="px-4 py-2.5 font-medium text-gray-900">{kw.keyword}</td>
                        <td className="px-4 py-2.5 text-gray-600">{kw.search_volume?.toLocaleString()}</td>
                        <td className="px-4 py-2.5">
                          {kw.current_position
                            ? <span className="font-semibold text-brand-600">#{kw.current_position}</span>
                            : <span className="text-gray-300 text-xs">—</span>}
                        </td>
                        <td className="px-4 py-2.5 text-green-600 font-semibold">
                          ${kw.opportunity_value?.toLocaleString()}
                        </td>
                        <td className="px-4 py-2.5 text-gray-600">{kw.top1_monthly_clicks?.toLocaleString()}</td>
                        <td className="px-4 py-2.5 font-medium text-gray-700">${kw.top1_monthly_revenue?.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="card p-8 text-center text-sm text-gray-400">
              Add tracked keywords to see ROI forecasts
            </div>
          )}
        </div>
      )}

      {/* ── TRAFFIC FORECAST ── */}
      {tab === "traffic" && (
        <div>
          {traffLoading ? (
            <div className="card p-8 text-center text-sm text-gray-400">Forecasting…</div>
          ) : traffic ? (
            <>
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="card px-5 py-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Trend</p>
                  <div className="flex items-center gap-2 mt-1">
                    {traffic.trend_direction === "rising"
                      ? <TrendingUp size={22} className="text-green-500" />
                      : traffic.trend_direction === "falling"
                      ? <TrendingDown size={22} className="text-red-500" />
                      : <Minus size={22} className="text-gray-400" />}
                    <span className="text-xl font-semibold capitalize text-gray-900">{traffic.trend_direction}</span>
                  </div>
                </div>
                <div className="card px-5 py-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Forecast 30d clicks</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">{traffic.forecast_30d_clicks?.toLocaleString()}</p>
                </div>
                <div className="card px-5 py-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Model confidence</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">{traffic.confidence}%</p>
                </div>
              </div>

              <div className="card p-5">
                <h3 className="text-sm font-medium text-gray-700 mb-4">Traffic forecast (90 days)</h3>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} interval={13}
                      tickFormatter={(v: string) => v.slice(5)} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e5e7eb" }} />
                    {lastHistoricalDate && (
                      <ReferenceLine x={lastHistoricalDate} stroke="#d1d5db" strokeDasharray="4 2"
                        label={{ value: "Today", position: "insideTopRight", fontSize: 11, fill: "#9ca3af" }} />
                    )}
                    <Line type="monotone" dataKey="clicks" stroke="#6366f1" strokeWidth={2} dot={false}
                      strokeDasharray={(d: any) => d.payload?.type === "forecast" ? "5 3" : "0"} />
                  </LineChart>
                </ResponsiveContainer>
                <p className="text-xs text-gray-400 mt-2 text-center">
                  Solid = historical · Dashed = forecast · Confidence: {traffic.confidence}%
                </p>
              </div>
            </>
          ) : (
            <div className="card p-8 text-center text-sm text-gray-400">
              Connect Google Search Console or run crawls to enable traffic forecasting
            </div>
          )}
        </div>
      )}
    </div>
  );
}
