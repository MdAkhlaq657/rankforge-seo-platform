"use client";
import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { tasksApi } from "@/lib/api";
import { Task, TaskBoardColumn, TaskStatus, Severity } from "@/types";
import SeverityBadge from "@/components/ui/SeverityBadge";
import { taskStatusLabel, formatDate, cn } from "@/lib/utils";
import { ArrowLeft, Plus, ExternalLink, User, Calendar } from "lucide-react";
import Link from "next/link";

const COLUMNS: { status: TaskStatus; label: string; color: string }[] = [
  { status: "open",        label: "Open",        color: "bg-gray-100 text-gray-600" },
  { status: "in_progress", label: "In Progress",  color: "bg-blue-100 text-blue-700" },
  { status: "in_review",   label: "In Review",    color: "bg-purple-100 text-purple-700" },
  { status: "done",        label: "Done",         color: "bg-green-100 text-green-700" },
];

const DIFFICULTY_COLOR: Record<string, string> = {
  low: "text-green-600",
  medium: "text-amber-600",
  high: "text-red-600",
};

function TaskCard({
  task,
  projectId,
  onStatusChange,
}: {
  task: Task;
  projectId: string;
  onStatusChange: (id: string, status: TaskStatus) => void;
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-100 p-3.5 shadow-sm hover:shadow transition-shadow">
      <div className="flex items-start justify-between gap-2 mb-2">
        <SeverityBadge severity={task.severity} />
        {task.affected_url && (
          <a
            href={task.affected_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-300 hover:text-brand-500 flex-shrink-0"
          >
            <ExternalLink size={13} />
          </a>
        )}
      </div>

      <p className="text-sm font-medium text-gray-900 leading-snug mb-2">{task.title}</p>

      {task.affected_url && (
        <p className="text-xs text-gray-400 font-mono truncate mb-2">
          {task.affected_url.replace(/^https?:\/\/[^/]+/, "") || "/"}
        </p>
      )}

      <div className="flex items-center justify-between mt-3 pt-2 border-t border-gray-50">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium ${DIFFICULTY_COLOR[task.fix_difficulty] ?? "text-gray-500"}`}>
            {task.fix_difficulty} effort
          </span>
        </div>
        <select
          value={task.status}
          onChange={(e) => onStatusChange(task.id, e.target.value as TaskStatus)}
          className="text-xs border-0 bg-transparent text-gray-400 hover:text-gray-700 cursor-pointer focus:outline-none pr-0"
          onClick={(e) => e.stopPropagation()}
        >
          {COLUMNS.map((col) => (
            <option key={col.status} value={col.status}>{col.label}</option>
          ))}
        </select>
      </div>
    </div>
  );
}

export default function TaskBoardPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const qc = useQueryClient();

  const { data: columns = [], isLoading } = useQuery<TaskBoardColumn[]>({
    queryKey: ["task-board", id],
    queryFn: async () => {
      const { data } = await tasksApi.getBoard(id);
      return data;
    },
  });

  const updateTask = useMutation({
    mutationFn: ({ taskId, status }: { taskId: string; status: TaskStatus }) =>
      tasksApi.update(id, taskId, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["task-board", id] }),
    onError: () => toast.error("Failed to update task"),
  });

  const handleStatusChange = (taskId: string, status: TaskStatus) => {
    updateTask.mutate({ taskId, status });
  };

  const totalTasks = columns.reduce((s, c) => s + c.count, 0);
  const doneTasks = columns.find((c) => c.status === "done")?.count ?? 0;
  const p1Count = columns
    .flatMap((c) => c.tasks)
    .filter((t) => t.severity === "p1" && t.status !== "done").length;

  return (
    <div>
      <Link href={`/projects/${id}`} className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5">
        <ArrowLeft size={14} /> Back to project
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Task board</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {totalTasks} tasks · {doneTasks} done
            {p1Count > 0 && (
              <span className="ml-2 text-red-600 font-medium">· {p1Count} P1 critical</span>
            )}
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-gray-100 rounded-xl h-64 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 items-start">
          {COLUMNS.map((col) => {
            const colData = columns.find((c) => c.status === col.status);
            const tasks = colData?.tasks ?? [];

            return (
              <div key={col.status} className="bg-gray-50/80 rounded-xl p-3">
                {/* Column header */}
                <div className="flex items-center justify-between mb-3 px-1">
                  <div className="flex items-center gap-2">
                    <span className={`badge ${col.color}`}>{col.label}</span>
                  </div>
                  <span className="text-xs text-gray-400 font-medium">{tasks.length}</span>
                </div>

                {/* Task cards */}
                <div className="space-y-2.5">
                  {tasks.length === 0 ? (
                    <div className="text-center py-6 text-xs text-gray-400">No tasks</div>
                  ) : (
                    tasks.map((task) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        projectId={id}
                        onStatusChange={handleStatusChange}
                      />
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Severity summary bar */}
      {!isLoading && totalTasks > 0 && (
        <div className="mt-8 card p-4">
          <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
            Issue breakdown
          </h3>
          <div className="grid grid-cols-3 gap-4 text-center">
            {(["p1", "p2", "p3"] as Severity[]).map((sev) => {
              const count = columns
                .flatMap((c) => c.tasks)
                .filter((t) => t.severity === sev && t.status !== "done" && t.status !== "resolved").length;
              return (
                <div key={sev}>
                  <p className={`text-2xl font-semibold ${
                    sev === "p1" ? "text-red-600" :
                    sev === "p2" ? "text-amber-600" : "text-blue-600"
                  }`}>{count}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {sev === "p1" ? "P1 Critical" : sev === "p2" ? "P2 Important" : "P3 Minor"}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
