import { useEffect, useState } from 'react';

interface Props {
  confidence: number;
}

export default function ConfidenceGauge({ confidence }: Props) {
  const [animated, setAnimated] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setAnimated(true), 200);
    return () => clearTimeout(t);
  }, [confidence]);

  const size = 110;
  const strokeWidth = 10;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - confidence * circumference;

  const color = confidence >= 0.8 ? 'var(--success)'
    : confidence >= 0.5 ? 'var(--accent)' : 'var(--danger)';

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      gap: 2, position: 'relative',
    }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="var(--border)" strokeWidth={strokeWidth}
        />
        <circle cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth={strokeWidth}
          strokeLinecap="round" strokeDasharray={circumference}
          strokeDashoffset={animated ? offset : circumference}
          style={{ transition: 'stroke-dashoffset 1.2s cubic-bezier(0.4,0,0.2,1)' }}
        />
      </svg>

      <div style={{
        position: 'absolute', top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
      }}>
        <div style={{
          fontWeight: 800, fontSize: '1.375rem', color,
          animation: animated ? 'number-pop 0.6s ease' : 'none',
        }}>
          {Math.round(confidence * 100)}%
        </div>
        <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginTop: -2 }}>
          Confidence
        </div>
      </div>
    </div>
  );
}
