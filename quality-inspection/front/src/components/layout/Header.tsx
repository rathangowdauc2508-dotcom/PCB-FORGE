import { useOrchestrationStore } from '../../stores/orchestrationStore';

export default function Header() {
  const { backendAvailable } = useOrchestrationStore();

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <a className="brand-lockup" href="http://localhost:3000/#forgeTransition=1" aria-label="PCB Forge manufacturing workspace">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" fill="none">
              <rect x="5" y="5" width="22" height="22" rx="4" stroke="currentColor" strokeWidth="1.7" />
              <path d="M10 11h5v5h6M10 21h4v-4m5 5h3v-3" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="10" cy="11" r="1.5" fill="currentColor" />
              <circle cx="22" cy="22" r="1.5" fill="currentColor" />
            </svg>
          </span>
          <span className="brand-copy">
            <span className="brand-title">PCB Forge</span>
            <span className="brand-tagline">PCB DESIGN · FABRICATION · QUALITY</span>
          </span>
        </a>

        <div className="header-actions">
          <span className={`service-status ${backendAvailable ? 'is-online' : 'is-offline'}`}>
            <span className="status-dot" />
            {backendAvailable ? 'Connected' : 'Offline'}
          </span>
          <a href="http://localhost:3000/#forgeTransition=1" className="btn header-workspace-link">
            PCB Manufacturing <span aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
    </header>
  );
}

