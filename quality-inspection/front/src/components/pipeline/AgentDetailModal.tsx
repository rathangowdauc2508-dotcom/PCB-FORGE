import type {
  AgentTrace,
  DesignOutput,
  PhysicalOutput,
  ResolutionOutput,
  SpecOutput,
  SymptomOutput,
} from '../../types/api';

const AGENT_DISPLAY: Record<string, { label: string; color: string }> = {
  agent_1: { label: 'Error Analyzer', color: 'var(--accent)' },
  agent_2a: { label: 'Spec Checker', color: '#c87137' },
  agent_2b: { label: 'CAD Mapper', color: '#0891b2' },
  agent_3: { label: 'Defect Inspector', color: 'var(--danger)' },
  agent_4: { label: 'Spec Resolution', color: 'var(--success)' },
};

const HANDOFF_DISPLAY: Record<string, string> = {
  agent_1: 'Error Analyzer',
  agent_2a: 'Spec Checker',
  agent_2b: 'CAD Mapper',
  'agent_2a,agent_2b': 'Spec Checker + CAD Mapper',
  agent_3: 'Defect Inspector',
  agent_4: 'Spec Resolution',
};

interface Props {
  trace: AgentTrace;
  onClose: () => void;
}

export default function AgentDetailModal({ trace, onClose }: Props) {
  const display = AGENT_DISPLAY[trace.agent_id] ?? { label: trace.agent_name, color: 'var(--accent)' };
  const handoffName = trace.handoff_to ? (HANDOFF_DISPLAY[trace.handoff_to] ?? trace.handoff_to) : null;

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.3)',
          zIndex: 199,
        }}
      />

      <div
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width: Math.min(560, window.innerWidth - 40),
          background: 'var(--card)',
          zIndex: 200,
          display: 'flex',
          flexDirection: 'column',
          animation: 'slide-in-right 0.25s ease-out',
          boxShadow: '-8px 0 32px rgba(0,0,0,0.12)',
        }}
      >
        <div
          style={{
            padding: '24px 28px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'var(--card-hover)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: display.color,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                fontWeight: 800,
                fontSize: '0.8125rem',
              }}
            >
              {trace.agent_id.replace('agent_', '').toUpperCase()}
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: '1.125rem', color: 'var(--text)' }}>{display.label}</div>
              {handoffName && (
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Hands off to {handoffName}</div>
              )}
            </div>
          </div>
          <button className="btn" onClick={onClose} style={{ padding: '6px 16px', fontSize: '0.875rem' }}>
            Close
          </button>
        </div>

        {trace.handoff_message && (
          <div style={{ padding: '14px 28px', borderBottom: '1px solid var(--border)' }}>
            <div
              style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                color: display.color,
                marginBottom: 6,
              }}
            >
              Handoff Message
            </div>
            <div
              style={{
                fontSize: '0.9375rem',
                color: 'var(--text-secondary)',
                lineHeight: 1.6,
                wordBreak: 'keep-all',
                overflowWrap: 'break-word',
              }}
            >
              {trace.handoff_message}
            </div>
          </div>
        )}

        <div style={{ flex: 1, overflow: 'auto', padding: '24px 28px' }}>
          <FormattedOutput agentId={trace.agent_id} output={trace.output} />
        </div>
      </div>
    </>
  );
}

function FormattedOutput({ agentId, output }: { agentId: string; output: Record<string, unknown> }) {
  if (agentId === 'agent_1') return <SymptomView data={output as unknown as SymptomOutput} />;
  if (agentId === 'agent_2a') return <SpecView data={output as unknown as SpecOutput} />;
  if (agentId === 'agent_2b') return <DesignView data={output as unknown as DesignOutput} />;
  if (agentId === 'agent_3') return <PhysicalView data={output as unknown as PhysicalOutput} />;
  if (agentId === 'agent_4') return <ResolutionView data={output as unknown as ResolutionOutput} />;
  return <RawJson data={output} />;
}

function SymptomView({ data }: { data: SymptomOutput }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {data.error_interpretation && (
        <Section title="Error Interpretation">
          <p style={{ fontSize: '0.9375rem', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
            {data.error_interpretation}
          </p>
        </Section>
      )}
      {data.suspect_parts?.length > 0 && (
        <Section title="Suspect Parts">
          {data.suspect_parts.map((part, i) => (
            <div key={i} style={{ padding: '12px 0', marginBottom: 4, borderBottom: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{part.part_name}</span>
                <span style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--danger)' }}>
                  {Math.round(part.confidence * 100)}%
                </span>
              </div>
              <div style={{ fontSize: '0.875rem', marginBottom: 6, color: 'var(--text)', lineHeight: 1.6 }}>
                Fault mode: {part.likely_fault_mode}
              </div>
              <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                {part.why_related}
              </div>
            </div>
          ))}
        </Section>
      )}
    </div>
  );
}

function SpecView({ data }: { data: SpecOutput }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {data.spec_risk_summary && (
        <Section title="Risk Summary">
          <p style={{ fontSize: '0.9375rem', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
            {data.spec_risk_summary}
          </p>
        </Section>
      )}
      {data.spec_watchlist?.length > 0 && (
        <Section title="Spec Watchlist">
          {data.spec_watchlist.map((item, i) => (
            <div key={i} style={{ padding: '12px 0', marginBottom: 4, borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontFamily: 'var(--mono)', fontSize: '0.8125rem', color: 'var(--accent)', marginBottom: 8, fontWeight: 600 }}>
                {item.rule_id}
              </div>
              <div style={{ fontSize: '0.9375rem', marginBottom: 8, lineHeight: 1.6, color: 'var(--text)' }}>
                {item.what_to_check}
              </div>
              <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                {item.why_relevant}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 6 }}>Priority: {item.priority}</div>
            </div>
          ))}
        </Section>
      )}
    </div>
  );
}

function DesignView({ data }: { data: DesignOutput }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {data.cad_mappings?.length > 0 && (
        <Section title="CAD Mappings">
          {data.cad_mappings.map((item, i) => (
            <div key={i} style={{ padding: '12px 0', marginBottom: 4, borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontWeight: 600, fontSize: '0.9375rem', marginBottom: 8 }}>{item.part_name}</div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontFamily: 'var(--mono)', marginBottom: 8 }}>
                {item.schematic_reference} | ({item.bbox.x1}, {item.bbox.y1}) to ({item.bbox.x2}, {item.bbox.y2})
              </div>
              <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>{item.reason}</div>
            </div>
          ))}
        </Section>
      )}
    </div>
  );
}

function PhysicalView({ data }: { data: PhysicalOutput }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {data.defect_verification?.length > 0 && (
        <Section title="Defect Verification">
          {data.defect_verification.map((item, i) => (
            <div key={i} style={{ padding: '12px 0', marginBottom: 4, borderBottom: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{item.defect_type}</span>
                <span style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--danger)' }}>
                  {Math.round(item.confidence * 100)}%
                </span>
              </div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontFamily: 'var(--mono)', marginBottom: 8 }}>
                {item.part_name} | ({item.bbox.x1}, {item.bbox.y1}) to ({item.bbox.x2}, {item.bbox.y2})
              </div>
              <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>{item.evidence}</div>
            </div>
          ))}
        </Section>
      )}
      {data.root_cause_candidate && (
        <Section title="Root Cause Candidate">
          <p style={{ fontSize: '0.9375rem', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
            {data.root_cause_candidate}
          </p>
        </Section>
      )}
      {data.impact && (
        <Section title="Impact">
          <p style={{ fontSize: '0.9375rem', lineHeight: 1.7, color: 'var(--text-secondary)' }}>{data.impact}</p>
        </Section>
      )}
    </div>
  );
}

function ResolutionView({ data }: { data: ResolutionOutput }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {data.final_root_cause && (
        <Section title="Final Root Cause">
          <p style={{ fontSize: '0.9375rem', lineHeight: 1.7, color: 'var(--text)', fontWeight: 600 }}>
            {data.final_root_cause}
          </p>
        </Section>
      )}
      {data.spec_checks?.length > 0 && (
        <Section title="Spec Checks">
          {data.spec_checks.map((check, i) => (
            <div key={i} style={{ padding: '12px 0', marginBottom: 4, borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontFamily: 'var(--mono)', fontSize: '0.8125rem', color: 'var(--accent)', marginBottom: 6 }}>
                {check.rule_id}
              </div>
              <div style={{ fontSize: '0.875rem', color: 'var(--text)', marginBottom: 6 }}>{check.rule_text}</div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--warning)', marginBottom: 6 }}>
                Status: {check.compliance_status}
              </div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>{check.gap}</div>
            </div>
          ))}
        </Section>
      )}
      {data.final_resolution?.length > 0 && (
        <Section title="Final Resolution">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.final_resolution.map((step, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, padding: '4px 0' }}>
                <span
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 22,
                    height: 22,
                    borderRadius: '50%',
                    flexShrink: 0,
                    background: 'var(--bg-alt)',
                    color: 'var(--text-secondary)',
                    fontSize: '0.6875rem',
                    fontWeight: 700,
                    border: '1px solid var(--border)',
                  }}
                >
                  {i + 1}
                </span>
                <span style={{ fontSize: '0.9375rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>{step}</span>
              </div>
            ))}
          </div>
        </Section>
      )}
      {data.final_confidence != null && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 0' }}>
          <span style={{ fontWeight: 700, color: 'var(--success)', fontSize: '1.25rem' }}>
            {Math.round(data.final_confidence * 100)}%
          </span>
          <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Final Confidence</span>
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div
        style={{
          fontSize: '0.75rem',
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          color: 'var(--text-muted)',
          marginBottom: 12,
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

function RawJson({ data }: { data: Record<string, unknown> }) {
  return (
    <pre
      className="mono"
      style={{
        background: 'var(--bg)',
        padding: 16,
        borderRadius: 10,
        overflow: 'auto',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        lineHeight: 1.6,
        color: 'var(--text-secondary)',
        border: '1px solid var(--border)',
      }}
    >
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

