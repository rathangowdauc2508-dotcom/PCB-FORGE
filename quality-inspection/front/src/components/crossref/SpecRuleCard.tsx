import type { SpecWatchItem } from '../../types/api';

interface Props {
  finding: SpecWatchItem;
  index: number;
  isHighlighted: boolean;
  onHover: (idx: number | null) => void;
}

export default function SpecRuleCard({ finding, index, isHighlighted, onHover }: Props) {
  return (
    <div
      onMouseEnter={() => onHover(index)}
      onMouseLeave={() => onHover(null)}
      style={{
        padding: '12px 0',
        borderBottom: '1px solid var(--border)',
        background: isHighlighted ? 'var(--accent-light)' : 'transparent',
        transition: 'all 0.25s', cursor: 'pointer',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span className="mono" style={{
          fontSize: '0.75rem', background: 'var(--accent-light)',
          color: 'var(--accent)', padding: '1px 6px', borderRadius: 'var(--radius-xs)', fontWeight: 600,
        }}>
          {finding.rule_id}
        </span>
      </div>
      <div style={{ fontSize: '0.875rem', marginBottom: 4, lineHeight: 1.6, color: 'var(--text)' }}>
        {finding.what_to_check}
      </div>
      <div style={{ fontSize: '0.8125rem', color: 'var(--warning)', fontWeight: 500 }}>
        Why: {finding.why_relevant}
      </div>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>
        Priority: {finding.priority}
      </div>
    </div>
  );
}
