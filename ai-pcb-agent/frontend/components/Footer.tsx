/**
 * Footer.
 *
 * Kept to a single hairline-separated row: attribution on the left, the stack
 * that actually matters for this project on the right. The year is computed
 * so it cannot go stale.
 */
export default function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="mt-14 border-t border-base-700 pt-6">
      <div className="flex flex-col items-center justify-between gap-3 sm:flex-row">
        <p className="text-xs text-base-600">
          &copy; {year}{" "}
          <span className="font-display font-semibold text-base-400">PCB Forge</span>
          . All rights reserved.
        </p>

        <p className="label-tech">
          PCB design · sourcing · inspection
        </p>
      </div>
    </footer>
  );
}
