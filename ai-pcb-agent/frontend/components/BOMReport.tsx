import type { BOMResult } from "@/types";
import { PackageCheck, PackageX, PackageMinus, Sparkles } from "lucide-react";

const icons: Record<string, JSX.Element> = {
  AVAILABLE: <PackageCheck className="h-4 w-4 text-accent-500" />,
  LOW_STOCK: <PackageMinus className="h-4 w-4 text-amber-400" />,
  UNAVAILABLE: <PackageX className="h-4 w-4 text-red-400" />,
};

export default function BOMReport({ bom }: { bom: BOMResult }) {
  return (
    <div className="rounded-2xl border border-base-700 bg-base-900/60 p-6 transition duration-200 hover:border-base-600 fade-in-up">
      <div className="flex items-center justify-between mb-4">
        <div><h3 className="text-lg font-semibold text-white">BOM / Component Analysis</h3><p className="mt-1 text-xs text-base-500">Availability and unit prices come from a bundled sample catalogue; verify with a distributor.</p></div>
        <span className="text-xs font-mono text-base-600">Estimate: ${bom.total_cost_usd.toFixed(2)} / unit</span>
      </div>

      <div className="space-y-2 mb-4 max-h-64 overflow-y-auto pr-1">
        {bom.items.map((item) => (
          <div key={item.part} className="flex items-start justify-between gap-3 rounded-lg bg-base-850 border border-base-700 p-3 text-sm transition duration-150 hover:-translate-y-px hover:border-accent-500/30">
            <div className="flex items-start gap-2 min-w-0">
              {icons[item.availability]}
              <div className="min-w-0">
                <div className="text-white font-mono text-sm truncate">{item.part}</div>
                <div className="text-base-600 text-xs">{item.description}</div><div className="mt-0.5 text-[10px] uppercase tracking-wide text-base-500">Sample catalogue: {item.availability.replace("_", " ")}</div>
                {item.alternatives.length > 0 && (
                  <div className="text-xs text-amber-400 mt-0.5">Alt: {item.alternatives.join(", ")}</div>
                )}
              </div>
            </div>
            <div className="text-right shrink-0">
              <div className="text-base-300 text-xs">×{item.quantity}</div>
              <div className="text-base-600 text-xs font-mono">${item.unit_cost_usd} est.</div>
            </div>
          </div>
        ))}
      </div>

      {bom.ai_status !== "available" && (
        <div className="mb-4 rounded-lg border border-base-700 bg-base-850 p-3 text-xs text-base-400">Gemma 4 explanation unavailable. Component extraction and displayed estimates remain separate from the AI review.</div>
      )}
      {bom.ai_summary && (
        <div className="rounded-lg border border-accent-500/20 bg-accent-500/5 p-3 text-sm text-base-200 transition-colors hover:border-accent-500/40">
          <div className="mb-2 flex items-center gap-2 label-tech text-accent-400">
            <Sparkles className="h-3.5 w-3.5" /> Gemma 4 BOM insight
          </div>
          <p className="leading-6">{bom.ai_summary}</p>
          {Boolean(bom.ai_evidence?.length) && (
            <details className="mt-3 border-t border-accent-500/15 pt-3">
              <summary className="cursor-pointer text-xs font-medium text-accent-300">Evidence used by Gemma 4</summary>
              <ul className="mt-2 space-y-2">
                {bom.ai_evidence!.map((evidence) => (
                  <li key={evidence.id} className="rounded-md border border-base-700/70 bg-base-900/40 px-3 py-2 text-xs">
                    <span className="mr-2 font-mono text-accent-400">{evidence.id}</span>
                    <span className="font-medium text-base-200">{evidence.label}</span>
                    <p className="mt-1 leading-5 text-base-400">{evidence.detail}</p>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
