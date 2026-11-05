import { useState } from 'react';
import { useOrchestrationStore } from '../../stores/orchestrationStore';
import AgentCard from './AgentCard';
import HandoffArrow from './HandoffArrow';
import AgentDetailModal from './AgentDetailModal';

export default function AgentPipeline() {
  const {
    agentStatuses, result, isRunning, currentAgentName, isSampleResult,
    expandedAgentIdx, setExpandedAgentIdx,
  } = useOrchestrationStore();

  const traces = result?.agent_trace ?? [];
  const allDone = agentStatuses.every((s) => s === 'done');

  // Auto-expand while running, collapse after done
  const [manualCollapsed, setManualCollapsed] = useState<boolean | null>(null);
  const collapsed = manualCollapsed ?? (allDone && !!result && !isSampleResult);

  const openDetail = (i: number) => {
    if (agentStatuses[i] === 'done' && traces[i]) setExpandedAgentIdx(i);
  };

  return (
    <section className="card" style={{ overflow: 'hidden' }}>
      {/* Collapsible header */}
      <div
        onClick={() => setManualCollapsed(!collapsed)}
        style={{
          padding: '10px 20px', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderBottom: collapsed ? 'none' : '1px solid var(--border)',
          background: 'var(--card)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            fontSize: '0.8125rem', fontWeight: 700, textTransform: 'uppercase',
            letterSpacing: '0.06em', color: 'var(--accent)',
          }}>
            AGENT PIPELINE
          </span>
          {isRunning && (
            <span style={{
              fontSize: '0.8125rem', color: 'var(--text-muted)',
            }}>
              {currentAgentName ? `Running: ${currentAgentName}` : 'Orchestrating 5 agents...'}
            </span>
          )}
          {!isRunning && result && (
            <span style={{
              fontSize: '0.8125rem', color: 'var(--text-muted)',
            }}>
              Analysis complete
            </span>
          )}
        </div>
        <span style={{
          fontSize: '0.75rem', color: 'var(--text-muted)',
          transform: collapsed ? 'rotate(0deg)' : 'rotate(180deg)',
          transition: 'transform 0.2s',
        }}>&#9650;</span>
      </div>

      {/* Pipeline body */}
      {!collapsed && (
        <div style={{ padding: 'var(--space-lg)', animation: 'fadeUp 0.3s ease' }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            gap: 0,
            overflowX: 'auto',
            padding: 'var(--space-sm) 0',
          }}>
            <AgentCard index={0} status={agentStatuses[0]} trace={traces[0]} onClick={() => openDetail(0)} />
            <HandoffArrow active={agentStatuses[0] === 'done'} />

            <div style={{
              display: 'flex', flexDirection: 'column',
              gap: 'var(--space-sm)',
            }}>
              <AgentCard index={1} status={agentStatuses[1]} trace={traces[1]} onClick={() => openDetail(1)} />
              <AgentCard index={2} status={agentStatuses[2]} trace={traces[2]} onClick={() => openDetail(2)} />
            </div>

            <HandoffArrow active={agentStatuses[1] === 'done' && agentStatuses[2] === 'done'} />
            <AgentCard index={3} status={agentStatuses[3]} trace={traces[3]} onClick={() => openDetail(3)} />
            <HandoffArrow active={agentStatuses[3] === 'done'} />
            <AgentCard index={4} status={agentStatuses[4]} trace={traces[4]} onClick={() => openDetail(4)} />
          </div>
        </div>
      )}

      {/* Agent detail drawer */}
      {expandedAgentIdx !== null && traces[expandedAgentIdx] && (
        <AgentDetailModal
          trace={traces[expandedAgentIdx]}
          onClose={() => setExpandedAgentIdx(null)}
        />
      )}
    </section>
  );
}
