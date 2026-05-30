import { cwvStatus } from "@/lib/utils";

interface CWVRowProps {
  lcp: number | null;
  cls: number | null;
  inp: number | null;
}

function Pill({ label, value, status }: { label: string; value: string; status: ReturnType<typeof cwvStatus> }) {
  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${status.bg} ${status.color}`}>
      <span className="font-semibold">{label}</span>
      <span className="opacity-80">{value}</span>
    </div>
  );
}

export default function CWVIndicator({ lcp, cls, inp }: CWVRowProps) {
  if (!lcp && !cls && !inp) return <span className="text-gray-400 text-xs">No data</span>;
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {lcp != null && <Pill label="LCP" value={`${lcp}s`} status={cwvStatus("lcp", lcp)} />}
      {cls != null && <Pill label="CLS" value={String(cls)} status={cwvStatus("cls", cls)} />}
      {inp != null && <Pill label="INP" value={`${inp}ms`} status={cwvStatus("inp", inp)} />}
    </div>
  );
}
