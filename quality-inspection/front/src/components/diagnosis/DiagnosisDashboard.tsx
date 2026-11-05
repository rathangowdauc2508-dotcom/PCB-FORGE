import { useOrchestrationStore } from '../../stores/orchestrationStore';
import ConfidenceGauge from './ConfidenceGauge';
import RootCauseCard from './RootCauseCard';
import ResolutionList from './ResolutionList';

export default function DiagnosisDashboard() {
  const { result } = useOrchestrationStore();
  if (!result) return null;

  const { output } = result;
  const defectCount = output.bounding_boxes.length;
  const issueSummary = defectCount
    ? `${defectCount} visible issue${defectCount === 1 ? '' : 's'} flagged for review`
    : 'No visible defect confirmed from the supplied evidence';
  const durationMs = new Date(result.ended_at).getTime() - new Date(result.started_at).getTime();
  const durationStr = durationMs < 1000 ? `${durationMs}ms` : `${(durationMs / 1000).toFixed(1)}s`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      {/* Header bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        borderBottom: '1px solid var(--border)', paddingBottom: 'var(--space-xs)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            fontSize: '0.875rem', fontWeight: 800, textTransform: 'uppercase',
            letterSpacing: '0.06em', color: 'var(--success)',
          }}>
            HARDWARE DIAGNOSIS & ROOT CAUSE REPORT
          </span>
        </div>
        <span style={{
          fontSize: '0.6875rem', padding: '3px 10px', borderRadius: 'var(--radius-xs)',
          background: 'var(--danger-light)', color: 'var(--danger)',
          fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.04em',
          border: '1px solid rgba(220,38,38,0.2)',
        }}>
          {defectCount ? 'Potential issue · verify' : 'No defect confirmed'}
        </span>
      </div>

      {/* Top Section: KPI Stats & Confidence Gauge */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'auto 1fr',
        gap: 'var(--space-md)',
        alignItems: 'center',
        background: 'var(--bg-alt)',
        padding: '14px 16px',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border)',
      }}>
        <ConfidenceGauge confidence={output.confidence} />

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: 8,
        }}>
          <div style={{
            background: 'var(--card)', padding: '8px 10px',
            borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
          }}>
            <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
              Fault Class
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--danger)', fontWeight: 700, marginTop: 2 }}>
              {issueSummary}
            </div>
          </div>

          <div style={{
            background: 'var(--card)', padding: '8px 10px',
            borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
          }}>
            <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
              Faulted Net / Pin
            </div>
            <div className="mono" style={{ fontSize: '0.8125rem', color: 'var(--accent)', fontWeight: 700, marginTop: 2 }}>
              Not determined from image
            </div>
          </div>

          <div style={{
            background: 'var(--card)', padding: '8px 10px',
            borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
          }}>
            <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
              Error Signature
            </div>
            <div className="mono" style={{ fontSize: '0.8125rem', color: 'var(--warning)', fontWeight: 700, marginTop: 2 }}>
              No error log supplied
            </div>
          </div>

          <div style={{
            background: 'var(--card)', padding: '8px 10px',
            borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
          }}>
            <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
              IPC Compliance
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--danger)', fontWeight: 700, marginTop: 2 }}>
              Not assessed
            </div>
          </div>
        </div>
      </div>

      {/* Root cause and impact */}
      <RootCauseCard rootCause={output.root_cause} impact={output.impact} />

      {/* Circuit Telemetry Breakdown */}
      <div style={{
        background: 'var(--card)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-sm)',
        padding: '12px 16px',
      }}>
        <div style={{
          fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase',
          letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: 8,
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)' }} />
          Evidence limits
        </div>
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px',
          fontSize: '0.8125rem', lineHeight: 1.6, color: 'var(--text-secondary)',
        }}>
          <div>
            <strong style={{ color: 'var(--text)' }}>Photo findings:</strong> Visual indications only
          </div>
          <div>
            <strong style={{ color: 'var(--text)' }}>Electrical behavior:</strong> Not measured
          </div>
          <div>
            <strong style={{ color: 'var(--text)' }}>Standards compliance:</strong> Not assessed
          </div>
          <div>
            <strong style={{ color: 'var(--text)' }}>Next step:</strong> Verify flagged areas with inspection tools
          </div>
        </div>
      </div>

      {/* Actionable Resolutions */}
      <ResolutionList resolutions={output.resolution} />

      {/* Run metadata footer */}
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        padding: '10px 12px', borderTop: '1px solid var(--border)',
        background: 'var(--bg-alt)', borderRadius: 'var(--radius-xs)',
      }}>
        {[
          { label: 'Model Pipeline', value: result.model_used },
          { label: 'Latency', value: durationStr },
          { label: 'Multi-Agent Flow', value: `${result.agent_trace.length} Agents Chained` },
          { label: 'Verified BBox', value: `${output.bounding_boxes.length} Defect Area` },
        ].map((m) => (
          <div key={m.label} style={{ fontSize: '0.75rem', textAlign: 'center' }}>
            <span style={{ color: 'var(--text-muted)' }}>{m.label}: </span>
            <span className="mono" style={{ color: 'var(--accent)', fontWeight: 700 }}>{m.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
