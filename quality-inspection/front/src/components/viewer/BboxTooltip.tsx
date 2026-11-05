interface Props {
  label: string;
  confidence: number;
  x: number;
  y: number;
}

export default function BboxTooltip({ label, confidence, x, y }: Props) {
  return (
    <div style={{
      position: 'absolute', left: x, top: y - 38,
      background: 'rgba(10,15,13,0.94)', backdropFilter: 'blur(8px)',
      color: '#fff', padding: '6px 12px', borderRadius: 6,
      fontSize: '0.8125rem', fontWeight: 500, whiteSpace: 'nowrap',
      pointerEvents: 'none', zIndex: 10, transform: 'translateX(-50%)',
      border: '1px solid rgba(200,113,55,0.35)',
    }}>
      {label} <span style={{ color: '#e4a16f' }}>({Math.round(confidence * 100)}%)</span>
    </div>
  );
}
