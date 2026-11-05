import type { AgentStatus } from '../../stores/orchestrationStore';
import type { AgentTrace } from '../../types/api';

const AGENT_META: Record<number, { name: string; desc: string }> = {
  0: { name: 'Error Analyzer', desc: 'Error code parsing & part ID' },
  1: { name: 'Spec Checker', desc: 'Standard compliance check' },
  2: { name: 'CAD Mapper', desc: 'Schematic location mapping' },
  3: { name: 'Defect Inspector', desc: 'Physical defect verification' },
  4: { name: 'Spec Resolution', desc: 'Spec-based resolution' },
};

interface Props {
  index: number;
  status: AgentStatus;
  trace?: AgentTrace;
  onClick: () => void;
}

export default function AgentCard({ index, status, trace, onClick }: Props) {
  const meta = AGENT_META[index] ?? { name: `Agent ${index + 1}`, desc: '' };
  const isRunning = status === 'running';
  const isDone = status === 'done';

  const label = index === 1 ? '2a' : index === 2 ? '2b' : index === 3 ? '3' : index === 4 ? '4' : '1';

  return (
    <div
      onClick={() => { if (isDone && trace) onClick(); }}
      onMouseEnter={(e) => {
        if (isDone && trace) {
          e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.1)';
          e.currentTarget.style.transform = 'translateY(-1px)';
        }
      }}
      onMouseLeave={(e) => {
        if (isDone && trace) {
          e.currentTarget.style.boxShadow = isDone ? '0 1px 6px rgba(22,163,74,0.08)' : 'none';
          e.currentTarget.style.transform = 'translateY(0)';
        }
      }}
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        gap: 8,
        padding: '16px 24px',
        borderRadius: 'var(--radius-sm)',
        border: `1.5px solid ${isRunning ? 'var(--accent)' : isDone ? 'var(--success)' : 'var(--border)'}`,
        background: isRunning ? 'var(--accent-light)' : isDone ? 'var(--success-light)' : 'var(--card)',
        cursor: isDone && trace ? 'pointer' : 'default',
        transition: 'all 0.25s ease',
        width: 200,
        animation: isRunning ? 'pulse-border 1.5s ease-in-out infinite' : 'none',
        boxShadow: isDone ? '0 1px 6px rgba(22,163,74,0.08)' : isRunning ? '0 2px 8px rgba(37,99,235,0.1)' : 'none',
      }}
    >
      {/* Agent badge */}
      <div style={{
        width: 36, height: 36, borderRadius: '50%',
        background: isRunning ? 'var(--accent)' : isDone ? 'var(--success)' : 'var(--bg-alt)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: (isRunning || isDone) ? '#fff' : 'var(--text-muted)',
        fontWeight: 700, fontSize: '0.8125rem',
        transition: 'all 0.3s',
      }}>
        {isRunning ? (
          <span style={{
            display: 'block', width: 18, height: 18,
            border: '2px solid rgba(255,255,255,0.3)',
            borderTopColor: '#fff', borderRadius: '50%',
            animation: 'spin-ring 0.7s linear infinite',
          }} />
        ) : isDone ? '\u2713' : label}
      </div>

      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontSize: '0.875rem', fontWeight: 600,
          color: status === 'idle' ? 'var(--text-muted)' : 'var(--text)',
          lineHeight: 1.3,
        }}>
          {meta.name}
        </div>
        <div style={{
          fontSize: '0.6875rem',
          color: isRunning ? 'var(--accent)' : 'var(--text-muted)',
          marginTop: 2, lineHeight: 1.3,
        }}>
          {isRunning ? 'Processing...' : isDone ? 'Complete' : meta.desc}
        </div>
        {isDone && trace?.model_used && (
          <div style={{ fontSize: '0.625rem', color: 'var(--text-muted)', marginTop: 4 }}>
            {trace.model_used}
          </div>
        )}
      </div>

      {isDone && trace && (
        <div style={{
          fontSize: '0.6875rem', color: 'var(--accent)', fontWeight: 500,
          opacity: 0.7,
        }}>
          View details
        </div>
      )}
    </div>
  );
}
