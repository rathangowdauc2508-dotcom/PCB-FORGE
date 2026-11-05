interface Props {
  src: string;
  label: string;
}

export default function AnalyzedImageViewer({ src, label }: Props) {
  if (!src) return null;

  return (
    <div>
      <div className="label">{label}</div>
      <div style={{
        borderRadius: 'var(--radius-sm)', overflow: 'hidden',
        border: '1px solid var(--border)', display: 'inline-block',
      }}>
        <img
          src={`data:image/png;base64,${src}`}
          alt={label}
          style={{ width: '100%', maxWidth: 440, display: 'block', borderRadius: 'var(--radius-sm)' }}
        />
      </div>
    </div>
  );
}
