"use client";
import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { backlinksApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ArrowLeft, RefreshCw, Download, Search, AlertTriangle, ShieldAlert } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend } from "recharts";

type Tab = "overview" | "backlinks" | "toxic" | "anchors" | "gap";

const DR_COLOR = (dr: number) =>
  dr >= 60 ? "#22c55e" : dr >= 30 ? "#f59e0b" : "#ef4444";

const TOXICITY_COLOR = (t: number) =>
  t >= 60 ? "#ef4444" : t >= 30 ? "#f59e0b" : "#22c55e";

export default function BacklinksPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [gapDomain, setGapDomain] = useState("");
  const [gapResult, setGapResult] = useState<any>(null);

  const { data: profile } = useQuery<any>({
    queryKey: ["bl-profile", id],
    queryFn: async () => { const { data } = await backlinksApi.profile(id); return data; },
  });

  const { data: backlinks = [], isLoading } = useQuery<any[]>({
    queryKey: ["backlinks", id],
    queryFn: async () => { const { data } = await backlinksApi.list(id, { limit: 200 }); return data; },
    enabled: tab === "backlinks" || tab === "overview",
  });

  const { data: toxic = [] } = useQuery<any[]>({
    queryKey: ["bl-toxic", id],
    queryFn: async () => { const { data } = await backlinksApi.disavowCandidates(id); return data; },
    enabled: tab === "toxic",
  });

  const { data: anchors = [] } = useQuery<any[]>({
    queryKey: ["bl-anchors", id],
    queryFn: async () => { const { data } = await backlinksApi.anchorDistribution(id); return data; },
    enabled: tab === "anchors",
  });

  const fetchBacklinks = useMutation({
    mutationFn: () => backlinksApi.fetch(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bl-profile", id] });
      qc.invalidateQueries({ queryKey: ["backlinks", id] });
      toast.success("Backlinks fetched!");
    },
    onError: () => toast.error("Fetch failed"),
  });

  const runGap = useMutation({
    mutationFn: () => backlinksApi.gapAnalysis(id, { competitor_domain: gapDomain }),
    onSuccess: (res) => { setGapResult(res.data); setTab("gap"); },
    onError: () => toast.error("Gap analysis failed"),
  });

  const downloadDisavow = () => {
    window.open(`/api/v1/projects/${id}/backlinks/disavow.txt`, "_blank");
  };

  const TABS: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "backlinks", label: `All backlinks (${backlinks.length})` },
    { id: "toxic", label: `Toxic (${toxic.length})` },
    { id: "anchors", label: "Anchor text" },
    { id: "gap", label: "Gap analysis" },
  ];

  const dofollow = backlinks.filter(b => b.is_dofollow).length;
  const nofollow = backlinks.length - dofollow;
  const typeData = [
    { name: "Dofollow", value: dofollow, fill: "#6366f1" },
    { name: "Nofollow", value: nofollow, fill: "#e2e8f0" },
  ];

  return (
    <div>
      <Link href={`/projects/${id}`} className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5">
        <ArrowLeft size={14} /> Back to project
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Backlink Analysis</h1>
          {profile && (
            <p className="text-sm text-gray-500 mt-0.5">
              {profile.total_backlinks?.toLocaleString()} backlinks · {profile.total_referring_domains?.toLocaleString()} referring domains
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={downloadDisavow} disabled={toxic.length === 0}>
            <Download size={14} /> Disavow.txt
          </button>
          <button className="btn-primary" onClick={() => fetchBacklinks.mutate()} disabled={fetchBacklinks.isPending}>
            <RefreshCw size={14} className={fetchBacklinks.isPending ? "animate-spin" : ""} />
            {fetchBacklinks.isPending ? "Fetching…" : "Fetch backlinks"}
          </button>
        </div>
      </div>

      {/* Profile cards */}
      {profile && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[
            { label: "Domain Rating", value: profile.domain_rating, color: DR_COLOR(profile.domain_rating) },
            { label: "Total backlinks", value: profile.total_backlinks?.toLocaleString() },
            { label: "Referring domains", value: profile.total_referring_domains?.toLocaleString() },
            { label: "Spam score", value: `${profile.spam_score}/100`, color: TOXICITY_COLOR(profile.spam_score || 0) },
          ].map(c => (
            <div key={c.label} className="card px-5 py-4">
              <p className="text-xs text-gray-500 uppercase tracking-wider font-medium">{c.label}</p>
              <p className="text-3xl font-bold mt-1" style={{ color: c.color || "#111827" }}>{c.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 mb-6 overflow-x-auto">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium -mb-px border-b-2 transition-colors whitespace-nowrap",
              tab === t.id ? "border-brand-600 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700"
            )}>{t.label}</button>
        ))}
      </div>

      {/* Overview */}
      {tab === "overview" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card p-5">
            <h3 className="text-sm font-medium text-gray-700 mb-4">Link type distribution</h3>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={typeData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value">
                  {typeData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                </Pie>
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="card p-5">
            <h3 className="text-sm font-medium text-gray-700 mb-4">Domain Rating distribution</h3>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={[
                { range: "0–20",  count: backlinks.filter(b => (b.domain_rating||0) <= 20).length },
                { range: "21–40", count: backlinks.filter(b => (b.domain_rating||0) > 20 && (b.domain_rating||0) <= 40).length },
                { range: "41–60", count: backlinks.filter(b => (b.domain_rating||0) > 40 && (b.domain_rating||0) <= 60).length },
                { range: "61–80", count: backlinks.filter(b => (b.domain_rating||0) > 60 && (b.domain_rating||0) <= 80).length },
                { range: "81+",   count: backlinks.filter(b => (b.domain_rating||0) > 80).length },
              ]}>
                <XAxis dataKey="range" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                <Bar dataKey="count" fill="#6366f1" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* All backlinks */}
      {tab === "backlinks" && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                {["Source domain", "Anchor text", "Target URL", "DR", "Toxicity", "Type", "Status"].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs text-gray-500 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {backlinks.slice(0, 100).map((b: any, i: number) => (
                <tr key={i} className="border-b border-gray-50 hover:bg-gray-50/60 transition-colors">
                  <td className="px-4 py-2.5">
                    <a href={b.source_url} target="_blank" rel="noopener noreferrer"
                      className="text-brand-600 hover:underline text-xs font-mono">{b.source_domain}</a>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-gray-600 max-w-xs truncate">{b.anchor_text || "(empty)"}</td>
                  <td className="px-4 py-2.5 text-xs font-mono text-gray-400 max-w-xs truncate">
                    {b.target_url?.replace(/^https?:\/\/[^/]+/, "") || "/"}
                  </td>
                  <td className="px-4 py-2.5 font-semibold text-xs" style={{ color: DR_COLOR(b.domain_rating || 0) }}>
                    {b.domain_rating ?? "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="text-xs font-medium" style={{ color: TOXICITY_COLOR(b.toxicity_score || 0) }}>
                      {b.toxicity_score}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={cn("badge text-xs", b.is_dofollow ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500")}>
                      {b.is_dofollow ? "dofollow" : "nofollow"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={cn("badge text-xs",
                      b.status === "live" ? "bg-green-100 text-green-700" :
                      b.status === "new" ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-500"
                    )}>{b.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Toxic */}
      {tab === "toxic" && (
        <div>
          {toxic.length === 0 ? (
            <div className="card p-10 text-center text-sm text-gray-400">No toxic backlinks detected</div>
          ) : (
            <>
              <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-3 flex items-center gap-2 mb-4 text-sm text-red-700">
                <ShieldAlert size={16} />
                {toxic.length} backlinks with toxicity score ≥ 60. Consider disavowing these.
              </div>
              <div className="card overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 bg-gray-50">
                      {["Domain", "Toxicity", "Spam score", "DR"].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs text-gray-500 font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {toxic.map((b: any, i: number) => (
                      <tr key={i} className="border-b border-gray-50">
                        <td className="px-4 py-2.5 text-sm font-mono text-gray-700">{b.source_domain}</td>
                        <td className="px-4 py-2.5"><span className="text-red-600 font-bold">{b.toxicity_score}</span></td>
                        <td className="px-4 py-2.5 text-gray-600">{b.spam_score}</td>
                        <td className="px-4 py-2.5 text-gray-600">{b.domain_rating ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* Anchors */}
      {tab === "anchors" && (
        <div className="card p-5">
          <h3 className="text-sm font-medium text-gray-700 mb-4">Top anchor texts</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={anchors.slice(0, 12)} layout="vertical">
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="anchor" type="category" width={140} tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} formatter={(v: any, n: any, p: any) => [`${v} (${p.payload.pct}%)`, "count"]} />
              <Bar dataKey="count" fill="#6366f1" radius={[0,4,4,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Gap */}
      {tab === "gap" && (
        <div>
          <div className="card p-5 mb-6">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Competitor backlink gap</h3>
            <div className="flex gap-3">
              <input className="input flex-1" placeholder="competitor.com" value={gapDomain}
                onChange={e => setGapDomain(e.target.value)} />
              <button className="btn-primary" onClick={() => runGap.mutate()} disabled={runGap.isPending || !gapDomain}>
                {runGap.isPending ? "Analyzing…" : <><Search size={14} /> Analyze</>}
              </button>
            </div>
          </div>
          {gapResult && (
            <div>
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="card px-5 py-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Your domains</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">{gapResult.own_referring_domains}</p>
                </div>
                <div className="card px-5 py-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Competitor domains</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">{gapResult.competitor_referring_domains}</p>
                </div>
                <div className="card px-5 py-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Gap (opportunities)</p>
                  <p className="text-3xl font-bold text-brand-600 mt-1">{gapResult.gap_count}</p>
                </div>
              </div>
              <div className="card p-5">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-medium text-gray-700">
                    Domains linking to {gapResult.competitor_domain} but not you
                  </h3>
                </div>
                <div className="flex flex-wrap gap-2">
                  {gapResult.gap_domains.map((d: string) => (
                    <span key={d} className="badge bg-purple-50 text-purple-700 border border-purple-200 text-xs font-mono">{d}</span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
