export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatDuration(startedAt: string, endedAt: string): string {
  const ms = new Date(endedAt).getTime() - new Date(startedAt).getTime();
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString();
}
