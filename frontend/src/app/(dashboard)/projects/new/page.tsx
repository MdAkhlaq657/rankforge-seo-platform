"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { projectsApi } from "@/lib/api";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function NewProjectPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    domain: "",
    crawl_frequency: "weekly",
    max_pages: 500,
    respect_robots_txt: true,
  });

  const mutation = useMutation({
    mutationFn: () => projectsApi.create(form),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Project created!");
      router.push(`/projects/${res.data.id}`);
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail ?? "Failed to create project");
    },
  });

  return (
    <div className="max-w-lg">
      <Link href="/projects" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-6">
        <ArrowLeft size={15} /> Back to projects
      </Link>
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">New project</h1>

      <form
        onSubmit={(e) => { e.preventDefault(); mutation.mutate(); }}
        className="card p-6 space-y-5"
      >
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Project name</label>
          <input
            className="input"
            placeholder="My Client — Homepage"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Domain</label>
          <input
            className="input font-mono"
            placeholder="example.com"
            value={form.domain}
            onChange={(e) => setForm({ ...form, domain: e.target.value })}
            required
          />
          <p className="text-xs text-gray-400 mt-1">Without https:// — e.g. example.com</p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Crawl frequency</label>
            <select
              className="input"
              value={form.crawl_frequency}
              onChange={(e) => setForm({ ...form, crawl_frequency: e.target.value })}
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
              <option value="manual">Manual only</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max pages</label>
            <input
              type="number"
              className="input"
              min={10}
              max={10000}
              value={form.max_pages}
              onChange={(e) => setForm({ ...form, max_pages: Number(e.target.value) })}
            />
          </div>
        </div>

        <label className="flex items-center gap-2.5 cursor-pointer">
          <input
            type="checkbox"
            className="w-4 h-4 accent-brand-600"
            checked={form.respect_robots_txt}
            onChange={(e) => setForm({ ...form, respect_robots_txt: e.target.checked })}
          />
          <span className="text-sm text-gray-700">Respect robots.txt</span>
        </label>

        <div className="flex gap-3 pt-2">
          <button type="submit" className="btn-primary flex-1 justify-center" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating…" : "Create project"}
          </button>
          <Link href="/projects" className="btn-secondary flex-1 justify-center text-center">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
