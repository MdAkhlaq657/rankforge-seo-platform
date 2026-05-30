"use client";
import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { competitorsApi, linkBuildingApi } from "@/lib/api";
import { cn, formatRelative } from "@/lib/utils";
import { ArrowLeft, Plus, RefreshCw, Bell, Globe, Trash2, Mail } from "lucide-react";

type Tab = "competitors" | "link-building";

const EVENT_ICONS: Record<string, string> = {
  new_content: "📄",
  backlink_gained: "📈",
  backlink_lost: "📉",
  rank_change: "🔄",
};

const STAGE_COLORS: Record<string, string> = {
  prospecting: "bg-gray-100 text-gray-600",
  qualified: "bg-blue-100 text-blue-700",
  contacted: "bg-purple-100 text-purple-700",
  followed_up: "bg-amber-100 text-amber-700",
  negotiating: "bg-orange-100 text-orange-700",
  placed: "bg-green-100 text-green-700",
  declined: "bg-red-100 text-red-600",
};

export default function CompetitorsPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("competitors");
  const [newDomain, setNewDomain] = useState("");
  const [expandedComp, setExpandedComp] = useState<string | null>(null);
  const [events, setEvents] = useState<Record<string, any[]>>({});
  const [newProspect, setNewProspect] = useState({ domain: "", contact_email: "", domain_rating: "" });
  const [showProspectForm, setShowProspectForm] = useState(false);

  // Competitors
  const { data: competitors = [] } = useQuery<any[]>({
    queryKey: ["competitors", id],
    queryFn: async () => { const { data } = await competitorsApi.list(id); return data; },
  });

  const addComp = useMutation({
    mutationFn: () => competitorsApi.add(id, { domain: newDomain.trim().toLowerCase() }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["competitors", id] }); setNewDomain(""); toast.success("Competitor added"); },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? "Failed"),
  });

  const removeComp = useMutation({
    mutationFn: (cid: string) => competitorsApi.remove(id, cid),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["competitors", id] }),
  });

  const checkComp = useMutation({
    mutationFn: (cid: string) => competitorsApi.check(id, cid),
    onSuccess: (res, cid) => {
      qc.invalidateQueries({ queryKey: ["competitors", id] });
      setEvents(prev => ({ ...prev, [cid]: res.data.events }));
      setExpandedComp(cid);
      toast.success(`${res.data.events_found} events detected`);
    },
    onError: () => toast.error("Check failed"),
  });

  const loadEvents = async (cid: string) => {
    if (expandedComp === cid) { setExpandedComp(null); return; }
    setExpandedComp(cid);
    if (events[cid]) return;
    const { data } = await competitorsApi.events(id, cid);
    setEvents(prev => ({ ...prev, [cid]: data }));
  };

  // Link building
  const { data: pipeline = [] } = useQuery<any[]>({
    queryKey: ["lb-pipeline", id],
    queryFn: async () => { const { data } = await linkBuildingApi.pipeline(id); return data; },
    enabled: tab === "link-building",
  });

  const addProspect = useMutation({
    mutationFn: () => linkBuildingApi.add(id, {
      domain: newProspect.domain,
      contact_email: newProspect.contact_email || undefined,
      domain_rating: newProspect.domain_rating ? Number(newProspect.domain_rating) : undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lb-pipeline", id] });
      setShowProspectForm(false);
      setNewProspect({ domain: "", contact_email: "", domain_rating: "" });
      toast.success("Prospect added");
    },
  });

  const updateStatus = useMutation({
    mutationFn: ({ lid, status }: { lid: string; status: string }) =>
      linkBuildingApi.update(id, lid, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lb-pipeline", id] }),
  });

  const totalProspects = pipeline.reduce((s: number, col: any) => s + col.count, 0);
  const placed = pipeline.find((c: any) => c.stage === "placed")?.count ?? 0;

  return (
    <div>
      <Link href={`/projects/${id}`} className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5">
        <ArrowLeft size={14} /> Back to project
      </Link>

      {/* Tab switcher */}
      <div className="flex gap-1 border-b border-gray-200 mb-6">
        {([["competitors", "Competitor Intelligence"], ["link-building", "Link Building CRM"]] as const).map(([t, l]) => (
          <button key={t} onClick={() => setTab(t)}
            className={cn("px-4 py-2.5 text-sm font-medium -mb-px border-b-2 transition-colors",
              tab === t ? "border-brand-600 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700"
            )}>{l}</button>
        ))}
      </div>

      {/* ── COMPETITORS ── */}
      {tab === "competitors" && (
        <div>
          <div className="flex items-center gap-3 mb-6">
            <input className="input max-w-xs" placeholder="competitor.com" value={newDomain}
              onChange={e => setNewDomain(e.target.value)}
              onKeyDown={e => e.key === "Enter" && newDomain && addComp.mutate()} />
            <button className="btn-primary" onClick={() => addComp.mutate()} disabled={!newDomain || addComp.isPending}>
              <Plus size={15} /> Add competitor
            </button>
          </div>

          {competitors.length === 0 ? (
            <div className="card p-10 text-center text-sm text-gray-400">No competitors tracked yet</div>
          ) : (
            <div className="card divide-y divide-gray-50">
              {competitors.map((c: any) => (
                <div key={c.id}>
                  <div className="px-5 py-4 flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0">
                      <Globe size={15} className="text-gray-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 text-sm">{c.name}</p>
                      <p className="text-xs text-gray-400">
                        Checked {c.last_checked_at ? formatRelative(c.last_checked_at) : "never"}
                      </p>
                    </div>
                    {c.unread_events > 0 && (
                      <span className="badge bg-red-100 text-red-600 text-xs">{c.unread_events} new</span>
                    )}
                    <button className="btn-secondary text-xs py-1" onClick={() => checkComp.mutate(c.id)}
                      disabled={checkComp.isPending}>
                      <RefreshCw size={12} className={checkComp.isPending ? "animate-spin" : ""} />
                      Check now
                    </button>
                    <button onClick={() => loadEvents(c.id)} className="btn-secondary text-xs py-1">
                      <Bell size={12} /> Events
                    </button>
                    <button onClick={() => removeComp.mutate(c.id)} className="text-gray-300 hover:text-red-500 ml-1">
                      <Trash2 size={14} />
                    </button>
                  </div>

                  {expandedComp === c.id && (
                    <div className="mx-5 mb-3 bg-gray-50 rounded-xl p-4">
                      {!events[c.id] || events[c.id].length === 0 ? (
                        <p className="text-xs text-gray-400">No events detected yet. Click "Check now" to scan.</p>
                      ) : (
                        <div className="space-y-2">
                          {events[c.id].map((ev: any, i: number) => (
                            <div key={i} className="flex gap-2 items-start">
                              <span className="text-sm mt-0.5">{EVENT_ICONS[ev.event_type] ?? "•"}</span>
                              <div>
                                <p className="text-sm font-medium text-gray-800">{ev.title}</p>
                                <p className="text-xs text-gray-500">{ev.description}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── LINK BUILDING ── */}
      {tab === "link-building" && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-gray-500">{totalProspects} prospects · {placed} links placed</p>
            <button className="btn-primary" onClick={() => setShowProspectForm(!showProspectForm)}>
              <Plus size={15} /> Add prospect
            </button>
          </div>

          {showProspectForm && (
            <div className="card p-5 mb-5">
              <div className="grid grid-cols-3 gap-3 mb-3">
                <input className="input" placeholder="domain.com" value={newProspect.domain}
                  onChange={e => setNewProspect({ ...newProspect, domain: e.target.value })} />
                <input className="input" placeholder="email (optional)" value={newProspect.contact_email}
                  onChange={e => setNewProspect({ ...newProspect, contact_email: e.target.value })} />
                <input className="input" placeholder="DR (optional)" type="number" value={newProspect.domain_rating}
                  onChange={e => setNewProspect({ ...newProspect, domain_rating: e.target.value })} />
              </div>
              <div className="flex gap-2">
                <button className="btn-primary" onClick={() => addProspect.mutate()} disabled={!newProspect.domain || addProspect.isPending}>
                  Add prospect
                </button>
                <button className="btn-secondary" onClick={() => setShowProspectForm(false)}>Cancel</button>
              </div>
            </div>
          )}

          {/* Pipeline board */}
          <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-3">
            {pipeline.map((col: any) => (
              <div key={col.stage} className="bg-gray-50 rounded-xl p-3 min-w-0">
                <div className="flex items-center justify-between mb-2">
                  <span className={`badge text-xs capitalize ${STAGE_COLORS[col.stage] ?? "bg-gray-100 text-gray-600"}`}>
                    {col.stage.replace(/_/g, " ")}
                  </span>
                  <span className="text-xs text-gray-400">{col.count}</span>
                </div>
                <div className="space-y-2">
                  {col.prospects.map((p: any) => (
                    <div key={p.id} className="bg-white rounded-lg border border-gray-100 p-2.5 shadow-sm">
                      <p className="text-xs font-medium text-gray-900 truncate">{p.domain}</p>
                      {p.domain_rating && (
                        <p className="text-xs text-gray-400 mt-0.5">DR {p.domain_rating}</p>
                      )}
                      <div className="flex items-center gap-1 mt-2">
                        <select
                          value={p.status || col.stage}
                          onChange={e => updateStatus.mutate({ lid: p.id, status: e.target.value })}
                          className="text-xs border-0 bg-gray-50 rounded px-1 py-0.5 text-gray-500 w-full"
                        >
                          {["prospecting","qualified","contacted","followed_up","negotiating","placed","declined"].map(s => (
                            <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
