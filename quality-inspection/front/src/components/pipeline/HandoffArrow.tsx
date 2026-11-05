interface Props {
  active: boolean;
}

export default function HandoffArrow({ active }: Props) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center',
      flexShrink: 0, padding: '0 8px',
    }}>
      <svg width="48" height="16" viewBox="0 0 48 16">
        <line x1="0" y1="8" x2="36" y2="8"
          stroke={active ? 'var(--accent)' : 'var(--border)'}
          strokeWidth="1.5"
          strokeDasharray={active ? 'none' : '4 3'}
          style={{ transition: 'stroke 0.5s' }}
        />
        {active && (
          <line x1="0" y1="8" x2="36" y2="8"
            stroke="var(--accent)" strokeWidth="1.5"
            strokeDasharray="3 5"
            style={{ animation: 'flow-dash 0.8s linear infinite' }}
          />
        )}
        <polygon points="35,3 48,8 35,13"
          fill={active ? 'var(--accent)' : 'var(--border)'}
          style={{ transition: 'fill 0.5s' }}
        />
      </svg>
    </div>
  );
}
