"use client";
import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { keywordsApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ArrowLeft, Plus, Search, Layers, ChevronDown, ChevronUp, Trash2, BookOpen } from "lucide-react";

const INTENT_COLORS: Record<string, string> = {
  informational: "bg-blue-100 text-blue-700",
  transactional: "bg-green-100 text-green-700",
  commercial:    "bg-purple-100 text-purple-700",
  navigational:  "bg-gray-100 text-gray-600",
  unknown:       "bg-gray-100 text-gray-400",
};

const KD_COLOR = (kd: number) =>
  kd <= 30 ? "text-green-600" : kd <= 60 ? "text-amber-600" : "text-red-600";

function KDBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${value <= 30 ? "bg-green-500" : value <= 60 ? "bg-amber-500" : "bg-red-500"}`}
          style={{ width: `${value}%` }}
        />
      </div>
      <span className={`text-xs font-medium ${KD_COLOR(value)}`}>{value}</span>
    </div>
  );
}

export default function KeywordsPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const qc = useQueryClient();
  const [tab, setTab] = useState<"tracked" | "research">("tracked");
  const [seedInput, setSeedInput] = useState("");
  const [researchResults, setResearchResults] = useState<any[]>([]);
  const [expandedPAA, setExpandedPAA] = useState<string | null>(null);
  const [paaData, setPaaData] = useState<Record<string, any[]>>({});
  const [intentFilter, setIntentFilter] = useState("all");

  const { data: keywords = [], isLoading } = useQuery<any[]>({
    queryKey: ["keywords", id, intentFilter],
    queryFn: async () => {
      const { data } = await keywordsApi.list(id, {
        intent: intentFilter !== "all" ? intentFilter : undefined,
      });
      return data;
    },
  });

  const research = useMutation({
    mutationFn: (kws: string[]) =>
      keywordsApi.research(id, { keywords: kws, track: false }),
    onSuccess: (res) => setResearchResults(res.data),
    onError: () => toast.error("Research failed"),
  });

  const addKeyword = useMutation({
    mutationFn: (kw: string) =>
      keywordsApi.research(id, { keywords: [kw], track: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["keywords", id] });
      toast.success("Keyword added to tracking");
    },
  });

  const deleteKw = useMutation({
    mutationFn: (kwId: string) => keywordsApi.delete(id, kwId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["keywords", id] }),
    onError: () => toast.error("Failed to delete"),
  });

  const cluster = useMutation({
    mutationFn: () => keywordsApi.cluster(id),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["keywords", id] });
      toast.success(`Clustered into ${res.data.clusters} groups`);
    },
  });

  const loadPAA = async (kwId: string, kwText: string) => {
    if (expandedPAA === kwId) { setExpandedPAA(null); return; }
    setExpandedPAA(kwId);
    if (paaData[kwId]) return;
    try {
      const { data } = await keywordsApi.paa(id, kwId);
      setPaaData(prev => ({ ...prev, [kwId]: data }));
    } catch { toast.error("Failed to load PAA"); }
  };

  const handleResearch = () => {
    const kws = seedInput.split("\n").map(k => k.trim()).filter(Boolean);
    if (!kws.length) { toast.error("Enter at least one keyword"); return; }
    if (kws.length > 50) { toast.error("Max 50 keywords"); return; }
    research.mutate(kws);
  };

  const intents = ["all", "informational", "commercial", "transactional", "navigational"];

  return (
    <div>
      <Link href={`/projects/${id}`} className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5">
        <ArrowLeft size={14} /> Back to project
      </Link>

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-gray-900">Keyword Research</h1>
        <div className="flex gap-2">
          <button
            className="btn-secondary"
            onClick={() => cluster.mutate()}
            disabled={cluster.isPending || keywords.length < 3}
          >
            <Layers size={15} />
            {cluster.isPending ? "Clustering…" : "Cluster keywords"}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 mb-6">
        {(["tracked", "research"] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium -mb-px border-b-2 transition-colors capitalize",
              tab === t ? "border-brand-600 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700"
            )}
          >
            {t === "tracked" ? `Tracked keywords (${keywords.length})` : "Research new"}
          </button>
        ))}
      </div>

      {/* TRACKED tab */}
      {tab === "tracked" && (
        <>
          {/* Intent filter */}
          <div className="flex items-center gap-2 mb-4 flex-wrap">
            {intents.map(i => (
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

          {isLoading ? (
            <div className="card p-8 text-center text-sm text-gray-400">Loading…</div>
          ) : keywords.length === 0 ? (
            <div className="card p-12 text-center">
              <Search size={36} className="mx-auto text-gray-200 mb-3" />
              <p className="font-medium text-gray-600">No tracked keywords yet</p>
              <p className="text-sm text-gray-400 mt-1 mb-4">Use the Research tab to find and add keywords</p>
              <button className="btn-primary inline-flex" onClick={() => setTab("research")}>
                <Plus size={15} /> Research keywords
              </button>
            </div>
          ) : (
            <div className="card divide-y divide-gray-50">
              {/* Header */}
              <div className="grid grid-cols-12 px-5 py-2.5 text-xs text-gray-500 font-medium uppercase tracking-wide bg-gray-50 rounded-t-xl">
                <div className="col-span-4">Keyword</div>
                <div className="col-span-2">Volume</div>
                <div className="col-span-2">Difficulty</div>
                <div className="col-span-2">Intent</div>
                <div className="col-span-1">Position</div>
                <div className="col-span-1" />
              </div>
              {keywords.map((kw: any) => (
                <div key={kw.id}>
                  <div className="grid grid-cols-12 px-5 py-3 items-center hover:bg-gray-50/60 transition-colors">
                    <div className="col-span-4">
                      <p className="text-sm font-medium text-gray-900">{kw.keyword}</p>
                      {kw.cluster_id && (
                        <span className="text-xs text-gray-400">{kw.cluster_id.replace("_", " ")}</span>
                      )}
                    </div>
                    <div className="col-span-2 text-sm text-gray-700 font-medium">
                      {kw.search_volume != null ? kw.search_volume.toLocaleString() : "—"}
                    </div>
                    <div className="col-span-2">
                      {kw.keyword_difficulty != null ? <KDBar value={kw.keyword_difficulty} /> : <span className="text-gray-400 text-xs">—</span>}
                    </div>
                    <div className="col-span-2">
                      <span className={`badge text-xs ${INTENT_COLORS[kw.intent] ?? "bg-gray-100 text-gray-500"}`}>
                        {kw.intent}
                      </span>
                    </div>
                    <div className="col-span-1 text-sm">
                      {kw.current_position != null
                        ? <span className="font-semibold text-brand-600">#{kw.current_position}</span>
                        : <span className="text-gray-400">—</span>}
                    </div>
                    <div className="col-span-1 flex items-center justify-end gap-2">
                      <button
                        onClick={() => loadPAA(kw.id, kw.keyword)}
                        title="People Also Ask"
                        className="text-gray-300 hover:text-brand-500 transition-colors"
                      >
                        <BookOpen size={14} />
                      </button>
                      <button
                        onClick={() => deleteKw.mutate(kw.id)}
                        className="text-gray-300 hover:text-red-500 transition-colors"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                  {/* PAA accordion */}
                  {expandedPAA === kw.id && (
                    <div className="mx-5 mb-3 bg-blue-50 border border-blue-100 rounded-lg p-4">
                      <p className="text-xs font-semibold text-blue-700 mb-2 uppercase tracking-wide">People Also Ask</p>
                      {paaData[kw.id] ? (
                        <ul className="space-y-1.5">
                          {paaData[kw.id].map((q: any, i: number) => (
                            <li key={i} className="text-sm text-gray-700">
                              <span className="text-blue-400 mr-1.5">Q.</span>{q.question}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-gray-400">Loading…</p>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* RESEARCH tab */}
      {tab === "research" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1">
            <div className="card p-5">
              <h3 className="text-sm font-medium text-gray-700 mb-3">Enter keywords</h3>
              <textarea
                className="input resize-none h-40 font-mono text-xs"
                placeholder={"seo software\nkeyword research tool\nbest rank tracker"}
                value={seedInput}
                onChange={e => setSeedInput(e.target.value)}
              />
              <p className="text-xs text-gray-400 mt-1.5">One keyword per line. Max 50.</p>
              <button
                className="btn-primary w-full justify-center mt-3"
                onClick={handleResearch}
                disabled={research.isPending}
              >
                <Search size={15} />
                {research.isPending ? "Researching…" : "Get keyword data"}
              </button>
            </div>
          </div>

          <div className="lg:col-span-2">
            {researchResults.length === 0 ? (
              <div className="card p-10 text-center text-sm text-gray-400">
                Results will appear here after research
              </div>
            ) : (
              <div className="card divide-y divide-gray-50">
                <div className="grid grid-cols-10 px-5 py-2.5 text-xs text-gray-500 font-medium uppercase tracking-wide bg-gray-50 rounded-t-xl">
                  <div className="col-span-4">Keyword</div>
                  <div className="col-span-2">Volume</div>
                  <div className="col-span-2">KD</div>
                  <div className="col-span-1">CPC</div>
                  <div className="col-span-1" />
                </div>
                {researchResults.map((kw: any, i: number) => (
                  <div key={i} className="grid grid-cols-10 px-5 py-3 items-center hover:bg-gray-50/60 transition-colors">
                    <div className="col-span-4">
                      <p className="text-sm font-medium text-gray-900">{kw.keyword}</p>
                      <span className={`badge text-xs ${INTENT_COLORS[kw.intent] ?? "bg-gray-100 text-gray-500"}`}>
                        {kw.intent}
                      </span>
                    </div>
                    <div className="col-span-2 text-sm text-gray-700 font-medium">
                      {kw.search_volume != null ? kw.search_volume.toLocaleString() : "—"}
                    </div>
                    <div className="col-span-2">
                      {kw.keyword_difficulty != null ? <KDBar value={kw.keyword_difficulty} /> : "—"}
                    </div>
                    <div className="col-span-1 text-sm text-gray-600">
                      {kw.cpc != null ? `$${kw.cpc.toFixed(2)}` : "—"}
                    </div>
                    <div className="col-span-1 flex justify-end">
                      <button
                        className="text-xs text-brand-600 hover:underline font-medium"
                        onClick={() => addKeyword.mutate(kw.keyword)}
                      >
                        + Track
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
