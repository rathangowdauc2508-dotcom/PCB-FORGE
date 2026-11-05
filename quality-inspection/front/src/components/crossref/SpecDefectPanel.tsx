import { useOrchestrationStore } from '../../stores/orchestrationStore';
import SpecRuleCard from './SpecRuleCard';
import type { SpecOutput, ResolutionOutput, PhysicalOutput } from '../../types/api';

export default function SpecDefectPanel() {
  const {
    result,
    highlightedSpecIdx,
    setHighlightedSpecIdx,
    setHighlightedBoxLabel,
    highlightedBoxLabel,
  } = useOrchestrationStore();

  if (!result) return null;

  const specTrace = result.agent_trace.find((t) => t.agent_id === 'agent_2a');
  const specOutput = specTrace?.output as unknown as SpecOutput | undefined;
  const findings = specOutput?.spec_watchlist ?? [];

  const resolutionTrace = result.agent_trace.find((t) => t.agent_id === 'agent_4');
  const resolutionOutput = resolutionTrace?.output as unknown as ResolutionOutput | undefined;
  const specChecks = resolutionOutput?.spec_checks ?? [];

  const physicalTrace = result.agent_trace.find((t) => t.agent_id === 'agent_3');
  const physicalOutput = physicalTrace?.output as unknown as PhysicalOutput | undefined;
  const defectVerifications = physicalOutput?.defect_verification ?? [];

  const bboxes = result.output.bounding_boxes;

  const handleHover = (idx: number | null, label?: string) => {
    setHighlightedSpecIdx(idx);
    if (label) {
      setHighlightedBoxLabel(label);
    } else if (idx !== null && bboxes[idx]) {
      setHighlightedBoxLabel(bboxes[idx].label);
    } else {
      setHighlightedBoxLabel(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: 'var(--space-xs)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
          <span style={{
            fontSize: '0.875rem', fontWeight: 800, textTransform: 'uppercase',
            letterSpacing: '0.06em', color: 'var(--warning)',
          }}>
            SPEC / DEFECT CROSS-REFERENCE
          </span>
        </div>
        <span style={{
          fontSize: '0.6875rem', padding: '2px 8px', borderRadius: 'var(--radius-xs)',
          background: bboxes.length > 0 ? 'var(--danger-light)' : 'var(--success-light)',
          color: bboxes.length > 0 ? 'var(--danger)' : 'var(--success)',
          fontWeight: 700,
        }}>
          {bboxes.length} Defect Box{bboxes.length === 1 ? '' : 'es'} Bound
        </span>
      </div>

      {/* Identified Defect Bounding Box Badges with interactive hover */}
      {bboxes.length > 0 && (
        <div style={{
          background: 'var(--bg-alt)',
          borderRadius: 'var(--radius-sm)',
          padding: '10px 12px',
          border: '1px solid var(--border)',
        }}>
          <div style={{
            fontSize: '0.6875rem', fontWeight: 700, color: 'var(--text-muted)',
            textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6,
          }}>
            Active Bounding Box Hotspots (Hover to Highlight)
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {bboxes.map((box, idx) => {
              const isSelected = highlightedBoxLabel === box.label || highlightedSpecIdx === idx;
              return (
                <button
                  key={idx}
                  onMouseEnter={() => handleHover(idx, box.label)}
                  onMouseLeave={() => handleHover(null)}
                  onClick={() => handleHover(idx, box.label)}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    padding: '4px 10px',
                    borderRadius: 'var(--radius-xs)',
                    border: `1.5px solid ${isSelected ? 'var(--danger)' : 'var(--border)'}`,
                    background: isSelected ? 'var(--danger-light)' : 'var(--card)',
                    color: isSelected ? 'var(--danger)' : 'var(--text)',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                >
                  <span style={{
                    width: 7, height: 7, borderRadius: '50%',
                    background: 'var(--danger)',
                  }} />
                  <span>{box.label}</span>
                  <span className="mono" style={{ fontSize: '0.6875rem', opacity: 0.8, color: 'var(--accent)' }}>
                    [{box.x1},{box.y1} → {box.x2},{box.y2}]
                  </span>
                  <span style={{
                    fontSize: '0.6875rem',
                    padding: '1px 5px',
                    borderRadius: 3,
                    background: 'rgba(0,0,0,0.06)',
                  }}>
                    {Math.round(box.confidence * 100)}%
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Verified Defect Physical Findings */}
      {defectVerifications.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{
            fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)',
            textTransform: 'uppercase', letterSpacing: '0.04em',
          }}>
            Physical Defect Verification
          </div>
          {defectVerifications.map((dv, i) => (
            <div
              key={i}
              onMouseEnter={() => handleHover(i, bboxes[i]?.label)}
              onMouseLeave={() => handleHover(null)}
              style={{
                padding: '10px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border)',
                background: highlightedSpecIdx === i ? 'var(--accent-light)' : 'var(--card)',
                transition: 'all 0.2s',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontWeight: 700, fontSize: '0.8125rem', color: 'var(--danger)' }}>
                  {dv.part_name} &bull; {dv.defect_type}
                </span>
                <span className="mono" style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
                  ROI: ({dv.bbox.x1}, {dv.bbox.y1}) to ({dv.bbox.x2}, {dv.bbox.y2})
                </span>
              </div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text)', lineHeight: 1.5 }}>
                {dv.evidence}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Compliance Rule Evaluations & Gaps */}
      {specChecks.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{
            fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)',
            textTransform: 'uppercase', letterSpacing: '0.04em',
          }}>
            Standard Compliance Checks (IPC / Spec)
          </div>
          {specChecks.map((sc, i) => {
            const isFailed = sc.compliance_status.toLowerCase() === 'fail';
            return (
              <div
                key={i}
                style={{
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-sm)',
                  border: `1px solid ${isFailed ? 'rgba(220,38,38,0.3)' : 'rgba(22,163,74,0.3)'}`,
                  background: isFailed ? 'var(--danger-light)' : 'var(--success-light)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span className="mono" style={{ fontWeight: 700, fontSize: '0.75rem', color: isFailed ? 'var(--danger)' : 'var(--success)' }}>
                    {sc.rule_id}
                  </span>
                  <span style={{
                    fontSize: '0.6875rem', fontWeight: 800, textTransform: 'uppercase',
                    padding: '2px 6px', borderRadius: 3,
                    background: isFailed ? 'var(--danger)' : 'var(--success)',
                    color: '#fff',
                  }}>
                    {sc.compliance_status}
                  </span>
                </div>
                <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text)', marginBottom: 2 }}>
                  {sc.rule_text}
                </div>
                <div style={{ fontSize: '0.75rem', color: isFailed ? 'var(--danger)' : 'var(--text-secondary)' }}>
                  <strong>Finding:</strong> {sc.gap}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Spec Watchlist Items */}
      {findings.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{
            fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)',
            textTransform: 'uppercase', letterSpacing: '0.04em',
          }}>
            Spec Inspection Watchlist
          </div>
          {findings.map((f, i) => (
            <SpecRuleCard
              key={i}
              finding={f}
              index={i}
              isHighlighted={highlightedSpecIdx === i}
              onHover={(idx) => handleHover(idx)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
