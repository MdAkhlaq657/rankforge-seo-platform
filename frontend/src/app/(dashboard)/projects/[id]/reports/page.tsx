"use client";
import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { reportsApi } from "@/lib/api";
import { cn, formatRelative } from "@/lib/utils";
import { ArrowLeft, FileBarChart, Plus, Download, Trash2, Loader2, Clock } from "lucide-react";

const STATUS_STYLES: Record<string, string> = {
  pending:   "bg-amber-100 text-amber-700",
  generated: "bg-green-100 text-green-700",
  failed:    "bg-red-100 text-red-700",
};

export default function ReportsPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", period_months: 1 });

  const { data: reports = [], isLoading } = useQuery<any[]>({
    queryKey: ["reports", id],
    queryFn: async () => { const { data } = await reportsApi.list(id); return data; },
    refetchInterval: (query) => {
      const r = query.state.data as any[] | undefined;
      return r?.some((rep: any) => rep.status === "pending") ? 5000 : false;
    },
  });

  const create = useMutation({
    mutationFn: () => reportsApi.create(id, form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reports", id] });
      setShowForm(false);
      toast.success("Report queued — ready in ~30 seconds");
    },
    onError: () => toast.error("Failed to queue report"),
  });

  const deleteReport = useMutation({
    mutationFn: (rid: string) => reportsApi.delete(id, rid),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reports", id] }),
  });

  const download = async (rid: string, title: string) => {
    try {
      const { data } = await reportsApi.download(id, rid);
      const url = URL.createObjectURL(new Blob([data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${title.replace(/ /g, "_")}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Download failed — report may still be generating");
    }
  };

  return (
    <div>
      <Link href={`/projects/${id}`} className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5">
        <ArrowLeft size={14} /> Back to project
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Reports</h1>
          <p className="text-sm text-gray-500 mt-0.5">Generate PDF reports for clients</p>
        </div>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
          <Plus size={15} /> Generate report
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="card p-5 mb-6">
          <h3 className="text-sm font-medium text-gray-700 mb-4">New report</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Report title (optional)</label>
              <input
                className="input"
                placeholder="Monthly SEO Report — October 2025"
                value={form.title}
                onChange={e => setForm({ ...form, title: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Period</label>
              <select
                className="input"
                value={form.period_months}
                onChange={e => setForm({ ...form, period_months: Number(e.target.value) })}
              >
                <option value={1}>Last month</option>
                <option value={3}>Last quarter (3 months)</option>
                <option value={6}>Last 6 months</option>
              </select>
            </div>
          </div>
          <p className="text-xs text-gray-400 mb-4">
            The report includes: executive summary, health score, CWV, top issues, keyword rankings, and GSC performance.
          </p>
          <div className="flex gap-2">
            <button className="btn-primary" onClick={() => create.mutate()} disabled={create.isPending}>
              {create.isPending ? <><Loader2 size={15} className="animate-spin" /> Queuing…</> : "Generate PDF"}
            </button>
            <button className="btn-secondary" onClick={() => setShowForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      {/* Reports list */}
      {isLoading ? (
        <div className="card p-8 text-center text-sm text-gray-400">Loading…</div>
      ) : reports.length === 0 ? (
        <div className="card p-12 text-center">
          <FileBarChart size={36} className="mx-auto text-gray-200 mb-3" />
          <p className="font-medium text-gray-600">No reports yet</p>
          <p className="text-sm text-gray-400 mt-1 mb-4">
            Generate your first client-ready PDF report
          </p>
          <button className="btn-primary inline-flex" onClick={() => setShowForm(true)}>
            <Plus size={15} /> Generate report
          </button>
        </div>
      ) : (
        <div className="card divide-y divide-gray-50">
          {reports.map((r: any) => (
            <div key={r.id} className="px-5 py-4 flex items-center gap-4">
              <div className={cn(
                "w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0",
                r.status === "generated" ? "bg-green-100" :
                r.status === "pending" ? "bg-amber-100" : "bg-red-100"
              )}>
                {r.status === "pending"
                  ? <Clock size={18} className="text-amber-600" />
                  : <FileBarChart size={18} className={r.status === "generated" ? "text-green-600" : "text-red-500"} />
                }
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{r.title}</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {r.period_start} – {r.period_end} · {formatRelative(r.created_at)}
                </p>
              </div>

              <span className={`badge text-xs ${STATUS_STYLES[r.status] ?? "bg-gray-100 text-gray-500"}`}>
                {r.status === "pending" ? "Generating…" : r.status}
              </span>

              <div className="flex items-center gap-2">
                {r.status === "generated" && r.has_pdf && (
                  <button
                    onClick={() => download(r.id, r.title)}
                    className="btn-secondary text-xs py-1.5 px-3"
                  >
                    <Download size={13} /> Download PDF
                  </button>
                )}
                <button
                  onClick={() => deleteReport.mutate(r.id)}
                  className="text-gray-300 hover:text-red-500 transition-colors"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
