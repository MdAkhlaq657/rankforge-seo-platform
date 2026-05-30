"use client";
import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { contentApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ArrowLeft, Wand2, Save, ChevronDown, ChevronRight, ExternalLink, Loader2 } from "lucide-react";

type Tab = "brief" | "article";

function BriefSection({ brief }: { brief: any }) {
  if (!brief || Object.keys(brief).length === 0)
    return <p className="text-sm text-gray-400">No brief data</p>;

  return (
    <div className="space-y-5">
      {/* Headline */}
      <div className="bg-brand-50 border border-brand-100 rounded-xl p-4">
        <p className="text-xs font-semibold text-brand-600 uppercase tracking-wider mb-1">Recommended title</p>
        <p className="text-base font-semibold text-gray-900">{brief.recommended_title}</p>
        {brief.meta_description && (
          <>
            <p className="text-xs font-semibold text-brand-600 uppercase tracking-wider mt-3 mb-1">Meta description</p>
            <p className="text-sm text-gray-600">{brief.meta_description}</p>
          </>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-50 rounded-lg p-3 text-center">
          <p className="text-xl font-bold text-gray-900">{brief.recommended_word_count?.toLocaleString()}</p>
          <p className="text-xs text-gray-500">Target words</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-3 col-span-2">
          <p className="text-xs font-semibold text-gray-600 mb-1">Content angle</p>
          <p className="text-sm text-gray-700">{brief.content_angle}</p>
        </div>
      </div>

      {/* Outline */}
      {brief.outline?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-2">Article outline</p>
          <div className="space-y-2">
            {brief.outline.map((section: any, i: number) => (
              <div key={i} className="border border-gray-100 rounded-lg overflow-hidden">
                <div className="bg-gray-50 px-4 py-2.5">
                  <p className="text-sm font-medium text-gray-900">H2: {section.heading}</p>
                </div>
                {section.subheadings?.length > 0 && (
                  <div className="px-4 py-2 space-y-1">
                    {section.subheadings.map((sub: string, j: number) => (
                      <p key={j} className="text-xs text-gray-500 pl-3 border-l-2 border-gray-200">
                        H3: {sub}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Questions & Entities */}
      <div className="grid grid-cols-2 gap-4">
        {brief.questions_to_answer?.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-2">Questions to answer</p>
            <ul className="space-y-1">
              {brief.questions_to_answer.map((q: string, i: number) => (
                <li key={i} className="text-xs text-gray-600 flex gap-1.5">
                  <span className="text-brand-400 flex-shrink-0">Q.</span>{q}
                </li>
              ))}
            </ul>
          </div>
        )}
        {brief.entities_to_include?.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-2">Entities to mention</p>
            <div className="flex flex-wrap gap-1.5">
              {brief.entities_to_include.map((e: string) => (
                <span key={e} className="badge bg-purple-50 text-purple-700 border border-purple-200 text-xs">{e}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {brief.writing_notes && (
        <div className="bg-amber-50 border border-amber-100 rounded-lg p-4">
          <p className="text-xs font-semibold text-amber-700 mb-1">Writing notes</p>
          <p className="text-sm text-gray-700">{brief.writing_notes}</p>
        </div>
      )}
    </div>
  );
}

export default function ContentDetailPage({ params }: { params: { id: string, contentId: string  } }) {
  const { id, contentId } = params;
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("brief");
  const [articleText, setArticleText] = useState("");
  const [edited, setEdited] = useState(false);

  const { data: piece, isLoading } = useQuery<any>({
    queryKey: ["content-piece", contentId],
    queryFn: async () => { const { data } = await contentApi.get(id, contentId); return data; },
    onSuccess: (data: any) => {
      if (data.article_markdown && !edited) setArticleText(data.article_markdown);
    },
  } as any);

  const generate = useMutation({
    mutationFn: () => contentApi.generateArticle(id, contentId),
    onSuccess: (res) => {
      setArticleText(res.data.article_markdown);
      qc.invalidateQueries({ queryKey: ["content-piece", contentId] });
      setTab("article");
      toast.success("Article generated!");
    },
    onError: (err: any) => toast.error(err.response?.data?.detail ?? "Generation failed"),
  });

  const save = useMutation({
    mutationFn: () => contentApi.update(id, contentId, { article_markdown: articleText }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["content-piece", contentId] });
      setEdited(false);
      toast.success("Saved");
    },
  });

  if (isLoading) return <div className="p-8 text-center text-sm text-gray-400">Loading…</div>;
  if (!piece) return null;

  return (
    <div>
      <Link href={`/projects/${id}/content`} className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5">
        <ArrowLeft size={14} /> Back to content
      </Link>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">{piece.title}</h1>
          <div className="flex items-center gap-3 mt-1">
            <span className="badge bg-gray-100 text-gray-600 text-xs">{piece.target_keyword}</span>
            <span className="badge bg-gray-100 text-gray-600 text-xs capitalize">{piece.status}</span>
            {piece.word_count && <span className="text-xs text-gray-400">{piece.word_count.toLocaleString()} words</span>}
          </div>
        </div>
        <div className="flex gap-2">
          {tab === "article" && edited && (
            <button className="btn-secondary" onClick={() => save.mutate()} disabled={save.isPending}>
              <Save size={14} /> {save.isPending ? "Saving…" : "Save"}
            </button>
          )}
          <button
            className="btn-primary"
            onClick={() => generate.mutate()}
            disabled={generate.isPending}
          >
            {generate.isPending ? (
              <><Loader2 size={15} className="animate-spin" /> Generating…</>
            ) : (
              <><Wand2 size={15} /> Generate article</>
            )}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 mb-6">
        {(["brief", "article"] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium -mb-px border-b-2 transition-colors capitalize",
              tab === t ? "border-brand-600 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700"
            )}
          >{t === "brief" ? "Content brief" : "Article editor"}</button>
        ))}
      </div>

      {tab === "brief" && (
        <div className="card p-6">
          <BriefSection brief={piece.brief} />
        </div>
      )}

      {tab === "article" && (
        <div className="card overflow-hidden">
          {(!piece.article_markdown && !articleText) ? (
            <div className="p-12 text-center">
              <Wand2 size={36} className="mx-auto text-gray-200 mb-3" />
              <p className="font-medium text-gray-600">No article yet</p>
              <p className="text-sm text-gray-400 mt-1 mb-4">
                Click "Generate article" to write a full SEO article based on the brief
              </p>
            </div>
          ) : (
            <textarea
              className="w-full h-[600px] p-6 text-sm font-mono text-gray-700 border-0 resize-none focus:outline-none focus:ring-0 leading-relaxed"
              value={articleText || piece.article_markdown || ""}
              onChange={e => { setArticleText(e.target.value); setEdited(true); }}
              placeholder="Article content will appear here…"
            />
          )}
        </div>
      )}

      {/* Competitor URLs */}
      {piece.competitor_urls?.length > 0 && (
        <div className="card p-4 mt-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Competitor pages analyzed
          </p>
          <div className="flex flex-wrap gap-2">
            {piece.competitor_urls.map((u: string) => (
              <a key={u} href={u} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs text-brand-600 hover:underline">
                <ExternalLink size={11} />
                {new URL(u).hostname}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
