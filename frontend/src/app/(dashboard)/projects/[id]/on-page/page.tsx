"use client";
import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { onpageApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ArrowLeft, Plus, ChevronRight, CheckCircle, AlertCircle } from "lucide-react";

function ScoreRing({ score }: { score: number }) {
  const r = 26;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  const color = score >= 75 ? "#22c55e" : score >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative w-16 h-16 flex items-center justify-center">
      <svg width="64" height="64" className="-rotate-90">
        <circle cx="32" cy="32" r={r} fill="none" stroke="#f3f4f6" strokeWidth="5" />
        <circle
          cx="32" cy="32" r={r} fill="none"
          stroke={color} strokeWidth="5"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
        />
      </svg>
      <span className="absolute text-sm font-bold" style={{ color }}>{score}</span>
    </div>
  );
}

export default function OnPagePage({ params }: { params: { id: string } }) {
  const { id } = params;
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ url: "", target_keyword: "", use_top_competitors: true });
  const [selected, setSelected] = useState<any>(null);

  const { data: analyses = [], isLoading } = useQuery<any[]>({
    queryKey: ["onpage", id],
    queryFn: async () => { const { data } = await onpageApi.list(id); return data; },
  });

  const analyze = useMutation({
    mutationFn: () => onpageApi.analyze(id, form),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["onpage", id] });
      setSelected(res.data);
      setShowForm(false);
      toast.success("Analysis complete");
    },
    onError: (err: any) => toast.error(err.response?.data?.detail ?? "Analysis failed"),
  });

  const loadDetail = async (analysisId: string) => {
    const { data } = await onpageApi.get(id, analysisId);
    setSelected(data);
  };

  return (
    <div>
      <Link href={`/projects/${id}`} className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5">
        <ArrowLeft size={14} /> Back to project
      </Link>

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-gray-900">On-Page NLP Analysis</h1>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
          <Plus size={15} /> New analysis
        </button>
      </div>

      {/* New analysis form */}
      {showForm && (
        <div className="card p-5 mb-6">
          <h3 className="text-sm font-medium text-gray-700 mb-4">Analyze a page</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Page URL</label>
              <input
                className="input"
                placeholder="https://example.com/your-page"
                value={form.url}
                onChange={e => setForm({ ...form, url: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Target keyword</label>
              <input
                className="input"
                placeholder="seo software"
                value={form.target_keyword}
                onChange={e => setForm({ ...form, target_keyword: e.target.value })}
              />
            </div>
          </div>
          <label className="flex items-center gap-2 mb-4 cursor-pointer">
            <input
              type="checkbox"
              className="accent-brand-600"
              checked={form.use_top_competitors}
              onChange={e => setForm({ ...form, use_top_competitors: e.target.checked })}
            />
            <span className="text-sm text-gray-700">Fetch top 5 competitors from SERP for comparison</span>
          </label>
          <div className="flex gap-2">
            <button
              className="btn-primary"
              onClick={() => analyze.mutate()}
              disabled={analyze.isPending || !form.url || !form.target_keyword}
            >
              {analyze.isPending ? "Analyzing…" : "Run analysis"}
            </button>
            <button className="btn-secondary" onClick={() => setShowForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* List */}
        <div className="lg:col-span-1">
          <div className="card divide-y divide-gray-50">
            {isLoading ? (
              <p className="p-5 text-sm text-gray-400">Loading…</p>
            ) : analyses.length === 0 ? (
              <p className="p-5 text-sm text-gray-400 text-center">No analyses yet</p>
            ) : analyses.map((a: any) => (
              <button
                key={a.id}
                onClick={() => loadDetail(a.id)}
                className={cn(
                  "w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors flex items-center gap-3",
                  selected?.id === a.id && "bg-brand-50"
                )}
              >
                <ScoreRing score={a.content_score ?? 0} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{a.target_keyword}</p>
                  <p className="text-xs text-gray-400 truncate font-mono">{a.url.replace(/^https?:\/\/[^/]+/, "") || "/"}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{a.word_count?.toLocaleString() ?? "—"} words</p>
                </div>
                <ChevronRight size={14} className="text-gray-300 flex-shrink-0" />
              </button>
            ))}
          </div>
        </div>

        {/* Detail panel */}
        <div className="lg:col-span-2">
          {!selected ? (
            <div className="card p-10 text-center text-sm text-gray-400">
              Select an analysis or run a new one
            </div>
          ) : (
            <div className="space-y-4">
              {/* Score + stats */}
              <div className="card p-5">
                <div className="flex items-center gap-5 mb-4">
                  <ScoreRing score={selected.content_score ?? 0} />
                  <div>
                    <h2 className="font-semibold text-gray-900">{selected.target_keyword}</h2>
                    <p className="text-xs text-gray-500 font-mono mt-0.5">{selected.url}</p>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-gray-900">{selected.word_count?.toLocaleString() ?? "—"}</p>
                    <p className="text-xs text-gray-500 mt-0.5">Your words</p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-gray-900">
                      {selected.avg_competitor_words ? selected.avg_competitor_words.toLocaleString() : "—"}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">Avg competitor</p>
                  </div>
                  <div className={cn(
                    "rounded-lg p-3 text-center",
                    selected.keyword_density >= 0.5 && selected.keyword_density <= 2.5
                      ? "bg-green-50"
                      : "bg-amber-50"
                  )}>
                    <p className={cn(
                      "text-2xl font-bold",
                      selected.keyword_density >= 0.5 && selected.keyword_density <= 2.5
                        ? "text-green-600" : "text-amber-600"
                    )}>{selected.keyword_density ?? "—"}%</p>
                    <p className="text-xs text-gray-500 mt-0.5">Keyword density</p>
                  </div>
                </div>
              </div>

              {/* Suggested keywords */}
              {selected.suggested_keywords?.length > 0 && (
                <div className="card p-5">
                  <h3 className="text-sm font-medium text-gray-700 mb-3">Suggested terms to include</h3>
                  <div className="flex flex-wrap gap-2">
                    {selected.suggested_keywords.map((kw: any) => (
                      <span key={kw.term} className="badge bg-brand-50 text-brand-700 border border-brand-200 text-xs">
                        {kw.term}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Missing entities */}
              {selected.missing_entities?.length > 0 && (
                <div className="card p-5">
                  <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                    <AlertCircle size={15} className="text-amber-500" />
                    Missing entities (found in competitors)
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {selected.missing_entities.slice(0, 20).map((e: string) => (
                      <span key={e} className="badge bg-amber-50 text-amber-700 border border-amber-200 text-xs">
                        {e}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Present entities */}
              {selected.present_entities?.length > 0 && (
                <div className="card p-5">
                  <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                    <CheckCircle size={15} className="text-green-500" />
                    Entities present on your page
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {selected.present_entities.slice(0, 20).map((e: string) => (
                      <span key={e} className="badge bg-green-50 text-green-700 border border-green-200 text-xs">
                        {e}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Competitors */}
              {selected.competitor_urls?.length > 0 && (
                <div className="card p-5">
                  <h3 className="text-sm font-medium text-gray-700 mb-3">Competitor pages analyzed</h3>
                  <ul className="space-y-1">
                    {selected.competitor_urls.map((u: string) => (
                      <li key={u}>
                        <a href={u} target="_blank" rel="noopener noreferrer"
                          className="text-xs text-brand-600 hover:underline font-mono">{u}</a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
