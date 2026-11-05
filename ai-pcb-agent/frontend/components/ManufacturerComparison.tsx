import type { ManufacturingRecommendation } from "@/types";
import { Sparkles, Clock, DollarSign, ShieldCheck, ShieldAlert } from "lucide-react";

interface Props {
  recommendation: ManufacturingRecommendation;
  selectedId: string;
  onSelect: (manufacturerId: string) => void;
}

export default function ManufacturerComparison({ recommendation, selectedId, onSelect }: Props) {
  const bestId = recommendation.recommended.manufacturer_id;

  return (
    <div className="rounded-2xl border border-base-700 bg-base-900/60 p-6 fade-in-up">
      <h3 className="text-lg font-semibold text-white mb-1">Supplier planning comparison</h3>
      <p className="mb-4 text-xs leading-5 text-base-500">Illustrative local catalogue only. Prices, lead times, and availability are estimates—not live quotes or stock. The internal score is a rule-based fit score, not a customer rating.</p>

      <div className="grid sm:grid-cols-3 gap-3 mb-4">
        {recommendation.all_quotes.map((q) => {
          const isBest = q.manufacturer_id === bestId;
          const isSelected = q.manufacturer_id === selectedId;
          return (
            <button
              key={q.manufacturer_id}
              onClick={() => onSelect(q.manufacturer_id)}
              className={`text-left rounded-xl border p-4 transition-all ${
                isSelected
                  ? "border-accent-500 bg-accent-500/5 shadow-glow"
                  : "border-base-700 bg-base-850 hover:border-base-600"
              }`}
            >
              {isBest && (
                <div className="flex items-center gap-1 text-accent-400 text-xs font-semibold mb-2">
                  <Sparkles className="h-3.5 w-3.5" /> RULE-BASED PICK
                </div>
              )}
              <div className="text-white font-semibold mb-2">{q.manufacturer_name}</div>
              <div className="flex items-center gap-1 text-sm text-base-200 mb-1">
                <DollarSign className="h-3.5 w-3.5 text-base-600" /> ${q.price_usd.toFixed(2)} estimate
              </div>
              <div className="flex items-center gap-1 text-sm text-base-200 mb-1">
                <Clock className="h-3.5 w-3.5 text-base-600" /> {q.lead_time_days} days estimated
              </div>
              <div className="flex items-center gap-1 text-sm mb-2">
                {q.dfm_compatible === true ? (
                  <ShieldCheck className="h-3.5 w-3.5 text-accent-500" />
                ) : q.dfm_compatible === false ? (
                  <ShieldAlert className="h-3.5 w-3.5 text-red-400" />
                ) : (
                  <ShieldAlert className="h-3.5 w-3.5 text-amber-400" />
                )}
                <span className={q.dfm_compatible === true ? "text-base-400" : q.dfm_compatible === false ? "text-red-400" : "text-amber-400"}>
                  {q.dfm_compatible === true ? "Meets listed limits" : q.dfm_compatible === false ? "Misses listed limits" : "DFM unverified"}
                </span>
              </div>
              <div className="text-xs font-mono text-base-600">Internal fit score: {q.score}/100</div>
            </button>
          );
        })}
      </div>

      <div className="rounded-lg border border-accent-500/20 bg-accent-500/5 p-3 text-sm text-base-200">
        <span className="label-tech text-xs text-base-500">{recommendation.ai_status === "available" ? "Gemma 4 interpretation" : "Rule-based explanation · Gemma 4 unavailable"}</span>
        <div className="mt-2">{recommendation.explanation}</div>
      </div>
    </div>
  );
}
