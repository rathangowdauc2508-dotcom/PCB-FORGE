"use client";

/**
 * TITLE BLOCK - the signature element.
 *
 * Every real PCB fabrication drawing carries a title block: a ruled strip of
 * labelled cells stating the board's defining facts. Using that device here
 * means the dashboard summary is written in the vernacular of the thing being
 * built, rather than as the usual row of big numbers on cards.
 *
 * The cells are ordered the way the workflow produces them - geometry, then
 * manufacturability, then cost, then sourcing, then settlement - so reading
 * left to right follows the agent pipeline. Cells fill in as each agent
 * reports, and read "—" until then.
 */

import type { AnalysisBundle } from "@/types";

interface Props {
  bundle: AnalysisBundle | null;
  selectedManufacturer?: string;
}

function Cell({
  label,
  value,
  unit,
  accent = false,
  wide = false,
}: {
  label: string;
  value: string;
  unit?: string;
  accent?: boolean;
  wide?: boolean;
}) {
  return (
    <div
      className={`border-b border-r border-base-700 px-4 py-3 last:border-r-0 ${
        wide ? "col-span-2" : ""
      }`}
    >
      <div className="label-tech">{label}</div>
      <div
        className={`mt-1 truncate font-mono text-sm font-medium ${
          accent ? "text-gold-500" : "text-base-100 text-[#E8EDE9]"
        }`}
        title={value}
      >
        {value}
        {unit && <span className="ml-1 text-xs text-base-600">{unit}</span>}
      </div>
    </div>
  );
}

export default function TitleBlock({
  bundle,
  selectedManufacturer,
}: Props) {
  const pcb = bundle?.pcb_analysis;
  const dfm = bundle?.dfm_result;
  const bom = bundle?.bom_result;
  const rec = bundle?.recommendation;

  const quote = rec?.all_quotes.find(
    (q) => q.manufacturer_id === (selectedManufacturer || rec?.recommended.manufacturer_id)
  );

  const dash = "—";

  return (
    <section
      aria-label="Board summary"
      className="fade-in-up overflow-hidden rounded-xl border border-base-700 bg-base-900/70"
    >
      {/* Drawing header strip */}
      <header className="flex items-center justify-between gap-4 border-b border-base-700 bg-base-850/60 px-4 py-2">
        <div className="flex items-center gap-3">
          <span className="label-tech">Fabrication summary</span>
          <span className="font-mono text-[10px] text-base-600">
            {pcb?.source ? pcb.source.replace("_", " ") : "awaiting upload"}
          </span>
        </div>
        <span className="label-tech">Units · mm</span>
      </header>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
        <Cell
          label="Board"
          value={pcb ? `${pcb.board_width_mm ?? "Unknown"} × ${pcb.board_height_mm ?? "Unknown"}` : dash}
        />
        <Cell label="Layers" value={pcb ? String(pcb.layers) : dash} />
        <Cell
          label="DFM"
          value={dfm ? `${dfm.passed_checks}/${dfm.total_checks} ${dfm.status}` : dash}
        />
        <Cell
          label="BOM cost estimate"
          value={bom ? `$${bom.total_cost_usd}` : dash}
          unit={bom ? "/unit" : undefined}
        />
        <Cell
          label="Illustrative supplier"
          value={quote ? quote.manufacturer_name : dash}
        />
        <Cell
          label="Lead time estimate"
          value={quote ? String(quote.lead_time_days) : dash}
          unit={quote ? "days" : undefined}
        />
      </div>

    </section>
  );
}
