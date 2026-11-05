import type {
  AnalysisResult,
  DemoCaseResponse,
  ModelsResponse,
  OrchestrationRequest,
  OrchestrationResponse,
  PCBDetectionResponse,
  LegacyPhotoInspectionResponse,
  TemplateStatus,
  UploadedOrchestrationRequest,
} from '../types/api';

const BASE = '/api';

export interface PCBDetectorStatus {
  detector: string;
  mode: 'yolo' | 'legacy-gemma';
  ready: boolean;
  ultralytics_installed: boolean;
  weights_found: boolean;
  weights_path: string;
  class_count: number;
  required_classes: string[];
  confidence_thresholds: Record<string, number>;
  yolo_ready?: boolean;
  gemini_available?: boolean;
  backend?: 'yolo' | 'gemini' | 'none';
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    let message = body;
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      if (typeof parsed.detail === 'string') message = parsed.detail;
    } catch { /* Keep the original response when it is not JSON. */ }
    throw new Error(message || `Request failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  models: () => request<ModelsResponse>('/models'),

  demoCase: () => request<DemoCaseResponse>('/demo-case'),

  orchestrate: (req: OrchestrationRequest, runId?: string) =>
    request<OrchestrationResponse>('/orchestrate', {
      method: 'POST',
      headers: runId ? { 'Content-Type': 'application/json', 'X-Run-ID': runId } : undefined,
      body: JSON.stringify(req),
    }),

  orchestrateUploaded: (req: UploadedOrchestrationRequest, runId?: string) =>
    request<OrchestrationResponse>('/orchestrate/uploaded', {
      method: 'POST',
      headers: runId ? { 'Content-Type': 'application/json', 'X-Run-ID': runId } : undefined,
      body: JSON.stringify(req),
    }),

  orchestrationProgress: (runId: string) =>
    request<{ stage: string }>(`/orchestrate/progress/${encodeURIComponent(runId)}`),

  detectPhotoDefects: (image: { mime_type: string; base64_data: string }, engine: 'auto' | 'trained' | 'gemini' = 'auto') =>
    request<PCBDetectionResponse>('/analysis/detect-defects', {
      method: 'POST', body: JSON.stringify({ image, engine }),
    }),

  inspectPhotoLegacy: (image: { mime_type: string; base64_data: string }) =>
    request<LegacyPhotoInspectionResponse>('/analysis/inspect-photo', {
      method: 'POST', body: JSON.stringify({ image }),
    }),

  pcbDetectorStatus: async (): Promise<PCBDetectorStatus> => {
    try {
      const current = await request<PCBDetectorStatus>('/analysis/detector-status');
      return current;
    } catch {
      // Keep the currently installed Gemma API usable while the user updates
      // their long-running backend process to the detector-enabled version.
      const schema = await request<{ paths?: Record<string, unknown> }>('/openapi.json');
      if (schema.paths?.['/analysis/inspect-photo']) {
        return {
          detector: 'Gemma 4 photo review (compatibility mode)',
          mode: 'legacy-gemma',
          ready: true,
          ultralytics_installed: false,
          weights_found: false,
          weights_path: '',
          class_count: 0,
          required_classes: [],
          confidence_thresholds: {},
        };
      }
      throw new Error('Inspection API is reachable but has no compatible PCB photo-inspection route. Restart the PCB Forge backend.');
    }
  },

  orchestrateDemo: (model?: string) =>
    request<OrchestrationResponse>('/orchestrate/demo', {
      method: 'POST',
      body: JSON.stringify({ model, include_raw_agent_payloads: true }),
    }),

  analysisTemplate: () => request<TemplateStatus>('/analysis/template'),

  analyze: async (file: File): Promise<AnalysisResult> => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${BASE}/analysis/analyze`, { method: 'POST', body: form });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`${res.status}: ${body}`);
    }
    return res.json();
  },
};
