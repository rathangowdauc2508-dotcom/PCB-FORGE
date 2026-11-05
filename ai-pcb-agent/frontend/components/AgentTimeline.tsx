import type { AgentEvent } from "@/types";
import { Check, Loader2, X } from "lucide-react";

/**
 * Agent activity log.
 *
 * The emoji icons are gone - they were decorative, inconsistent in weight,
 * and competed with the status glyph on the right for the same job. The agent
 * name now carries the emphasis instead, so the eye reads WHO acted, then
 * WHAT happened.
 *
 * A "running" event is superseded once a later event from the same agent
 * arrives (agents emit running then a separate done event, so untreated they
 * spin forever). The backend also normalizes this, so stale rows cannot spin
 * even on an older build.
 */
export default function AgentTimeline({ events }: { events: AgentEvent[] }) {
  if (events.length === 0) return null;

  const lastIndexByAgent = new Map<string, number>();
  events.forEach((e, i) => lastIndexByAgent.set(e.agent, i));

  const pipelineDone = events.some(
    (e) => e.status === "done" && /complete|confirmed|approval/i.test(e.message)
  );

  return (
    <div className="fade-in-up overflow-hidden rounded-xl border border-base-700 bg-base-900/70">
      <header className="border-b border-base-700 bg-base-850/60 px-4 py-2">
        <span className="label-tech">Agent activity</span>
      </header>

      <ol className="divide-y divide-base-800">
        {events.map((e, i) => {
          const superseded =
            e.status === "running" &&
            (pipelineDone || (lastIndexByAgent.get(e.agent) ?? i) > i);
          const status = superseded ? "done" : e.status;

          return (
            <li key={e.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
              <span className="flex h-4 w-4 shrink-0 items-center justify-center">
                {status === "running" && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-accent-400" />
                )}
                {status === "done" && (
                  <Check
                    className={`h-3.5 w-3.5 ${
                      superseded ? "text-base-600" : "text-accent-500"
                    }`}
                  />
                )}
                {status === "error" && <X className="h-3.5 w-3.5 text-red-400" />}
              </span>

              <span
                className={`shrink-0 font-semibold ${
                  status === "error"
                    ? "text-red-400"
                    : superseded
                    ? "text-base-600"
                    : "text-[#E8EDE9]"
                }`}
              >
                {e.agent}
              </span>

              <span
                className={`min-w-0 truncate ${
                  superseded ? "text-base-600" : "text-base-400"
                }`}
              >
                {e.message}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
