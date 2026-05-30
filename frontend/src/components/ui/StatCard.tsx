import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  color?: "default" | "green" | "red" | "amber" | "blue";
  icon?: React.ReactNode;
}

const colorMap = {
  default: "text-gray-900",
  green:   "text-green-600",
  red:     "text-red-600",
  amber:   "text-amber-600",
  blue:    "text-brand-600",
};

export default function StatCard({ label, value, sub, color = "default", icon }: StatCardProps) {
  return (
    <div className="card px-5 py-4">
      <div className="flex items-start justify-between">
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">{label}</p>
        {icon && <span className="text-gray-300">{icon}</span>}
      </div>
      <p className={cn("text-3xl font-semibold mt-1", colorMap[color])}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}
