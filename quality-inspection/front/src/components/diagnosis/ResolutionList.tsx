interface Props {
  resolutions: string[];
}

export default function ResolutionList({ resolutions }: Props) {
  return (
    <div style={{ animation: 'fadeUp 0.6s ease' }}>
      <div style={{
        fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase',
        letterSpacing: '0.06em', color: 'var(--text-muted)', marginBottom: 'var(--space-sm)',
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--success)' }} />
        Actionable Engineering Resolution Steps
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
        {resolutions.map((r, i) => (
          <div key={i} style={{
            display: 'flex', gap: 10, padding: '10px 12px',
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            alignItems: 'flex-start',
          }}>
            <span style={{
              flexShrink: 0, fontSize: '0.75rem', fontWeight: 800,
              background: 'var(--accent)', color: '#fff',
              width: 20, height: 20, borderRadius: '50%',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {i + 1}
            </span>
            <span style={{
              fontSize: '0.875rem', color: 'var(--text)', lineHeight: 1.5,
              wordBreak: 'keep-all', overflowWrap: 'break-word',
            }}>
              {r}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
