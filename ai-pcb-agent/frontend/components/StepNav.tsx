"use client";

/**
 * Step navigation.
 *
 * The workflow IS a sequence - a board is parsed, then checked, then sourced,
 * then paid for, then ordered - so numbering encodes something true rather
 * than decorating the layout. That is the test for using numbered markers at
 * all, and this content passes it.
 *
 * Completed steps are clickable so the demo can jump back to any screen
 * (useful when a judge asks "show me the DFM again"). Steps ahead of the
 * work are locked, because there is nothing there yet.
 */

import { Check, Lock } from "lucide-react";

export interface Step {
  id: number;
  label: string;
  /** false when the data this step needs does not exist yet */
  unlocked: boolean;
}

interface Props {
  steps: Step[];
  current: number;
  onSelect: (id: number) => void;
}

export default function StepNav({ steps, current, onSelect }: Props) {
  return (
    <nav aria-label="Workflow steps" className="overflow-x-auto">
      <ol className="flex min-w-max items-stretch rounded-xl border border-base-700 bg-base-900/70">
        {steps.map((step, i) => {
          const isCurrent = step.id === current;
          const isDone = step.unlocked && step.id < current;
          const isLocked = !step.unlocked;

          return (
            <li key={step.id} className="flex-1">
              <button
                onClick={() => step.unlocked && onSelect(step.id)}
                disabled={isLocked}
                aria-current={isCurrent ? "step" : undefined}
                className={`flex w-full items-center gap-2.5 px-4 py-3 text-left transition-colors ${
                  i > 0 ? "border-l border-base-700" : ""
                } ${
                  isCurrent
                    ? "bg-accent-500/10"
                    : isLocked
                    ? "cursor-not-allowed"
                    : "hover:bg-base-850"
                }`}
              >
                <span
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded font-mono text-[10px] font-semibold ${
                    isCurrent
                      ? "bg-accent-500 text-base-950"
                      : isDone
                      ? "bg-accent-500/15 text-accent-400"
                      : "bg-base-800 text-base-600"
                  }`}
                >
                  {isDone ? (
                    <Check className="h-3 w-3" />
                  ) : isLocked ? (
                    <Lock className="h-2.5 w-2.5" />
                  ) : (
                    String(step.id).padStart(2, "0")
                  )}
                </span>
                <span
                  className={`truncate text-xs font-semibold ${
                    isCurrent
                      ? "text-[#E8EDE9]"
                      : isLocked
                      ? "text-base-600"
                      : "text-base-400"
                  }`}
                >
                  {step.label}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
