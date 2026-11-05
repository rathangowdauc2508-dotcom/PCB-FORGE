import type { PCBAnalysis } from "@/types";
import { Ruler, Layers, Cpu, CircuitBoard, Waypoints, Grid2x2 } from "lucide-react";

export default function PCBOverview({ pcb }: { pcb: PCBAnalysis }) {
  const stats = [
    { label: "Board Size", value: `${pcb.board_width_mm ?? "Unknown"} × ${pcb.board_height_mm ?? "Unknown"} mm`, icon: Ruler },
    { label: "Layers", value: pcb.layers, icon: Layers },
    { label: "Components", value: pcb.components, icon: Cpu },
    { label: "Vias", value: pcb.vias, icon: CircuitBoard },
    { label: "Tracks", value: pcb.tracks, icon: Waypoints },
    { label: "Zones", value: pcb.zones, icon: Grid2x2 },
  ];

  return (
    <div className="rounded-2xl border border-base-700 bg-base-900/60 p-6 fade-in-up">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">PCB Overview</h3>
        <span className="text-xs font-mono text-base-600 uppercase">{pcb.source.replace("_", " ")}</span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {stats.map((s) => (
          <div key={s.label} className="rounded-xl bg-base-850 border border-base-700 p-4">
            <s.icon className="h-4 w-4 text-accent-400 mb-2" />
            <div className="text-xl font-semibold text-white font-mono">{s.value}</div>
            <div className="text-xs text-base-600 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
