"use client";
import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { contentApi } from "@/lib/api";
import { cn, formatRelative } from "@/lib/utils";
import { ArrowLeft, Plus, PenTool, FileText, Loader2, Trash2, ArrowRight } from "lucide-react";

const STATUS_BADGE: Record<string, string> = {
  draft:     "bg-gray-100 text-gray-600",
  generated: "bg-green-100 text-green-700",
  published: "bg-brand-100 text-brand-700",
};

export default function ContentPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", target_keyword: "" });

  const { data: pieces = [], isLoading } = useQuery<any[]>({
    queryKey: ["content", id],
    queryFn: async () => { const { data } = await contentApi.list(id); return data; },
  });

  const create = useMutation({
    mutationFn: () => contentApi.create(id, form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["content", id] });
      setShowForm(false);
      setForm({ title: "", target_keyword: "" });
      toast.success("Content piece created with brief");
    },
    onError: (err: any) => toast.error(err.response?.data?.detail ?? "Failed to create"),
  });

  const deletePiece = useMutation({
    mutationFn: (cid: string) => contentApi.delete(id, cid),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["content", id] }),
    onError: () => toast.error("Delete failed"),
  });

  return (
    <div>
      <Link href={`/projects/${id}`} className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5">
        <ArrowLeft size={14} /> Back to project
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">AI Content Writer</h1>
          <p className="text-sm text-gray-500 mt-0.5">Generate SEO briefs and full articles</p>
        </div>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
          <Plus size={15} /> New piece
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="card p-5 mb-6">
          <h3 className="text-sm font-medium text-gray-700 mb-4">Create content piece</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Target keyword</label>
              <input
                className="input"
                placeholder="best seo software 2025"
                value={form.target_keyword}
                onChange={e => setForm({ ...form, target_keyword: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Working title</label>
              <input
                className="input"
                placeholder="The Best SEO Software in 2025"
                value={form.title}
                onChange={e => setForm({ ...form, title: e.target.value })}
              />
            </div>
          </div>
          <p className="text-xs text-gray-400 mb-4">
            We'll scrape the top SERP results, extract competitor content, and generate a full brief automatically.
            {" "}{!process.env.NEXT_PUBLIC_ANTHROPIC_AVAILABLE && "Mock brief will be generated — add ANTHROPIC_API_KEY for real AI content."}
          </p>
          <div className="flex gap-2">
            <button
              className="btn-primary"
              onClick={() => create.mutate()}
              disabled={create.isPending || !form.target_keyword || !form.title}
            >
              {create.isPending ? (
                <><Loader2 size={15} className="animate-spin" /> Generating brief…</>
              ) : (
                <><PenTool size={15} /> Create & generate brief</>
              )}
            </button>
            <button className="btn-secondary" onClick={() => setShowForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      {/* Content list */}
      {isLoading ? (
        <div className="card p-8 text-center text-sm text-gray-400">Loading…</div>
      ) : pieces.length === 0 ? (
        <div className="card p-12 text-center">
          <PenTool size={36} className="mx-auto text-gray-200 mb-3" />
          <p className="font-medium text-gray-600">No content pieces yet</p>
          <p className="text-sm text-gray-400 mt-1 mb-4">
            Create a piece to generate an AI brief and full article
          </p>
          <button className="btn-primary inline-flex" onClick={() => setShowForm(true)}>
            <Plus size={15} /> Create first piece
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {pieces.map((p: any) => (
            <div key={p.id} className="card p-5 flex flex-col">
              <div className="flex items-start justify-between mb-3">
                <span className={`badge text-xs ${STATUS_BADGE[p.status] ?? "bg-gray-100 text-gray-600"}`}>
                  {p.status}
                </span>
                <button
                  onClick={() => deletePiece.mutate(p.id)}
                  className="text-gray-200 hover:text-red-500 transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>

              <h3 className="font-medium text-gray-900 text-sm leading-snug mb-1">{p.title}</h3>
              <p className="text-xs text-gray-500 mb-3">
                <span className="badge bg-gray-50 text-gray-500 border border-gray-200">{p.target_keyword}</span>
              </p>

              <div className="flex items-center gap-3 text-xs text-gray-400 mb-4">
                {p.word_count && <span>{p.word_count.toLocaleString()} words</span>}
                {p.seo_score && <span>SEO {p.seo_score}/100</span>}
                <span>{formatRelative(p.created_at)}</span>
              </div>

              <div className="mt-auto">
                <Link
                  href={`/projects/${id}/content/${p.id}`}
                  className="btn-secondary w-full justify-center text-sm"
                >
                  Open editor <ArrowRight size={13} />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
