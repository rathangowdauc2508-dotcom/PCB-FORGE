import { useState } from 'react';
import type { BoundingBox } from '../../types/api';
import BboxTooltip from './BboxTooltip';

interface Props {
  boxes: BoundingBox[];
  imgWidth: number;
  imgHeight: number;
  naturalWidth: number;
  naturalHeight: number;
  color: string;
  highlightedLabel: string | null;
  onHoverLabel: (label: string | null) => void;
  onClickLabel?: (label: string) => void;
}

export default function BoundingBoxOverlay({
  boxes, imgWidth, imgHeight, naturalWidth, naturalHeight,
  color, highlightedLabel, onHoverLabel, onClickLabel,
}: Props) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const scaleX = imgWidth / naturalWidth;
  const scaleY = imgHeight / naturalHeight;

  return (
    <svg width={imgWidth} height={imgHeight}
      style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none' }}
    >
      {boxes.map((box, i) => {
        const x = box.x1 * scaleX;
        const y = box.y1 * scaleY;
        const w = (box.x2 - box.x1) * scaleX;
        const h = (box.y2 - box.y1) * scaleY;
        const isHighlighted = highlightedLabel === box.label;
        const isHovered = hoveredIdx === i;
        const active = isHighlighted || isHovered;

        return (
          <g key={i}>
            {/* Glow effect */}
            {active && (
              <rect x={x - 2} y={y - 2} width={w + 4} height={h + 4}
                fill="transparent" stroke={color} strokeWidth={1}
                opacity={0.3} rx={4}
                style={{ filter: `blur(4px)` }}
              />
            )}
            {/* Main rect */}
            <rect x={x} y={y} width={w} height={h}
              fill={active ? `${color}15` : 'transparent'}
              stroke={color} strokeWidth={active ? 2.5 : 1.5}
              rx={3} opacity={active ? 1 : 0.7}
              style={{
                pointerEvents: 'all', cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={() => { setHoveredIdx(i); onHoverLabel(box.label); }}
              onMouseLeave={() => { setHoveredIdx(null); onHoverLabel(null); }}
              onClick={() => onClickLabel?.(box.label)}
            />
            {/* Corner marks */}
            {active && <>
              <line x1={x} y1={y} x2={x + 8} y2={y} stroke={color} strokeWidth={3} />
              <line x1={x} y1={y} x2={x} y2={y + 8} stroke={color} strokeWidth={3} />
              <line x1={x + w} y1={y} x2={x + w - 8} y2={y} stroke={color} strokeWidth={3} />
              <line x1={x + w} y1={y} x2={x + w} y2={y + 8} stroke={color} strokeWidth={3} />
              <line x1={x} y1={y + h} x2={x + 8} y2={y + h} stroke={color} strokeWidth={3} />
              <line x1={x} y1={y + h} x2={x} y2={y + h - 8} stroke={color} strokeWidth={3} />
              <line x1={x + w} y1={y + h} x2={x + w - 8} y2={y + h} stroke={color} strokeWidth={3} />
              <line x1={x + w} y1={y + h} x2={x + w} y2={y + h - 8} stroke={color} strokeWidth={3} />
            </>}
            {/* Tooltip */}
            {active && (
              <foreignObject x={x + w / 2 - 70} y={y - 44} width={140} height={44}>
                <BboxTooltip label={box.label} confidence={box.confidence} x={70} y={40} />
              </foreignObject>
            )}
          </g>
        );
      })}
    </svg>
  );
}
