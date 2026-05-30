import { Severity } from "@/types";
import { severityBadge, severityLabel } from "@/lib/utils";

export default function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`badge text-xs ${severityBadge(severity)}`}>
      {severityLabel(severity)}
    </span>
  );
}
