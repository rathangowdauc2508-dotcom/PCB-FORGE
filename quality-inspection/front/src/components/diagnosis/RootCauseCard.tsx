interface Props {
  rootCause: string;
  impact: string;
}

export default function RootCauseCard({ rootCause, impact }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)', animation: 'fadeUp 0.5s ease' }}>
      {/* Root Cause Card */}
      <div style={{
        background: 'var(--card)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-sm)',
        padding: '14px 16px',
        boxShadow: 'var(--shadow-sm)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8,
        }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%', background: 'var(--danger)',
          }} />
          <span style={{
            fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase',
            letterSpacing: '0.06em', color: 'var(--text-muted)',
          }}>
            Grounded Root Cause
          </span>
        </div>
        <div style={{
          fontSize: '0.9375rem', lineHeight: 1.7,
          color: 'var(--text)', fontWeight: 600,
        }}>
          {rootCause}
        </div>
      </div>

      {/* Impact Card */}
      <div style={{
        background: 'var(--bg-alt)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-sm)',
        padding: '12px 16px',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6,
        }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%', background: 'var(--warning)',
          }} />
          <span style={{
            fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase',
            letterSpacing: '0.06em', color: 'var(--text-muted)',
          }}>
            Hardware & System Impact
          </span>
        </div>
        <div style={{
          fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6,
        }}>
          {impact}
        </div>
      </div>
    </div>
  );
}
