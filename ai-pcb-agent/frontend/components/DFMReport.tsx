import type { DFMResult } from "@/types";
import { AlertTriangle, Check, Sparkles } from "lucide-react";

const statusStyles: Record<string, string> = {
  PASS: "text-accent-400 border-accent-500/30 bg-accent-500/10",
  WARNING: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  FAIL: "text-red-400 border-red-500/30 bg-red-500/10",
};

const severityColor: Record<string, string> = {
  LOW: "text-base-400",
  MEDIUM: "text-amber-400",
  HIGH: "text-red-400",
};

export default function DFMReport({ dfm }: { dfm: DFMResult }) {
  const unavailable = dfm.checks.filter((check) => check.passed === null);
  const failed = dfm.checks.filter((check) => check.passed === false);
  const passed = dfm.checks.filter((check) => check.passed === true);

  return (
    <section className="rounded-2xl border border-base-700 bg-base-900/60 p-6 fade-in-up">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-lg font-semibold text-white">DFM summary</h3>
        <span className={`rounded-full border px-2.5 py-1 text-xs font-mono font-semibold uppercase ${statusStyles[dfm.status] ?? statusStyles.WARNING}`}>
          {dfm.status}
        </span>
      </div>

      <p className="text-sm font-medium text-base-200">
        {passed.length} of {dfm.total_checks} checks passed
        {unavailable.length > 0 && ` · ${unavailable.length} not evaluated`}
        {failed.length > 0 && ` · ${failed.length} need review`}
      </p>
      <p className="mt-1 text-sm leading-6 text-base-400">
        {failed.length > 0
          ? "Review the flagged checks before manufacturing."
          : unavailable.length > 0
            ? "Some measurements are missing from this board file. Not evaluated does not mean failed."
            : "The available design checks passed. Confirm your manufacturer’s requirements before ordering."}
      </p>

      {(failed.length > 0 || dfm.issues.length > 0) && (
        <div className="mt-4 space-y-2">
          {dfm.issues.slice(0, 2).map((issue, index) => (
            <div key={`${issue.type}-${index}`} className="rounded-lg border border-base-700 bg-base-850 p-3 text-sm">
              <div className="flex items-center gap-2"><AlertTriangle className={`h-4 w-4 shrink-0 ${severityColor[issue.severity] ?? "text-amber-400"}`} /><span className="font-medium text-base-200">{issue.message}</span></div>
              <p className="mt-1 pl-6 text-xs text-base-500">
                {issue.type === "layer_count"
                  ? `Measured ${issue.actual} layers · manufacturer limit ${issue.required} layers`
                  : `Measured ${issue.actual} mm · minimum ${issue.required} mm`}
              </p>
            </div>
          ))}
        </div>
      )}

      <details className="mt-4 border-t border-base-800 pt-3">
        <summary className="cursor-pointer text-xs font-medium text-base-300">View check details ({dfm.checks.length})</summary>
        <ul className="mt-3 space-y-2">
          {dfm.checks.map((check) => (
            <li key={check.name} className="flex items-center gap-2 text-sm">
              {check.passed === true
                ? <Check className="h-4 w-4 shrink-0 text-accent-400" />
                : <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />}
              <span className={check.passed === true ? "text-base-200" : "text-base-400"}>
                {check.name} · {check.passed === true ? "Pass" : check.passed === false ? "Review" : "Not evaluated"}
              </span>
            </li>
          ))}
          {dfm.issues.slice(2).map((issue, index) => (
            <li key={`${issue.type}-extra-${index}`} className="text-xs text-base-400">{issue.message} · measured {issue.actual} mm, minimum {issue.required} mm</li>
          ))}
        </ul>
        {dfm.ai_summary && unavailable.length === 0 && (
          <div className="mt-4 rounded-lg border border-accent-500/20 bg-accent-500/5 p-3 text-sm text-base-300">
            <div className="mb-1 flex items-center gap-2 label-tech text-accent-400"><Sparkles className="h-3.5 w-3.5" /> AI advisory explanation</div>
            <p className="leading-6">{dfm.ai_summary}</p>
          </div>
        )}
      </details>
    </section>
  );
}
