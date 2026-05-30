import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { Severity, TaskStatus, CrawlStatus } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function severityBadge(severity: Severity) {
  return {
    p1: "bg-red-100 text-red-800 border border-red-200",
    p2: "bg-amber-100 text-amber-800 border border-amber-200",
    p3: "bg-blue-100 text-blue-700 border border-blue-200",
  }[severity] ?? "bg-gray-100 text-gray-700";
}

export function severityLabel(severity: Severity) {
  return { p1: "P1 Critical", p2: "P2 Important", p3: "P3 Minor" }[severity] ?? severity;
}

export function taskStatusLabel(status: TaskStatus) {
  return {
    open: "Open",
    in_progress: "In Progress",
    in_review: "In Review",
    done: "Done",
    resolved: "Resolved",
  }[status] ?? status;
}

export function crawlStatusColor(status: CrawlStatus) {
  return {
    pending: "text-gray-500",
    running: "text-blue-600",
    completed: "text-green-600",
    failed: "text-red-600",
    cancelled: "text-gray-400",
  }[status] ?? "text-gray-500";
}

export function crawlStatusBadge(status: CrawlStatus) {
  return {
    pending: "bg-gray-100 text-gray-600",
    running: "bg-blue-100 text-blue-700 animate-pulse",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
    cancelled: "bg-gray-100 text-gray-500",
  }[status] ?? "bg-gray-100 text-gray-600";
}

export function cwvStatus(metric: "lcp" | "cls" | "inp", value: number) {
  const thresholds = {
    lcp: { good: 2.5, poor: 4.0 },
    cls: { good: 0.1, poor: 0.25 },
    inp: { good: 200, poor: 500 },
  };
  const t = thresholds[metric];
  if (value <= t.good) return { label: "Good", color: "text-green-600", bg: "bg-green-100" };
  if (value <= t.poor) return { label: "Needs work", color: "text-amber-600", bg: "bg-amber-100" };
  return { label: "Poor", color: "text-red-600", bg: "bg-red-100" };
}

export function formatDate(date: string | null | undefined) {
  if (!date) return "—";
  return new Date(date).toLocaleDateString("en-GB", {
    day: "numeric", month: "short", year: "numeric",
  });
}

export function formatRelative(date: string | null | undefined) {
  if (!date) return "Never";
  const diff = Date.now() - new Date(date).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}
