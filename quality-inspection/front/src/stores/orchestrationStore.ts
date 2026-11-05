import { create } from 'zustand';
import type {
  DemoCaseResponse,
  ModelsResponse,
  OrchestrationResponse,
  PCBDetectionResponse,
  UploadedFileInput,
} from '../types/api';
import { api } from '../api/client';
import { buildDemoResponse, DEMO_INPUT } from '../api/demoData';

export type AgentStatus = 'idle' | 'running' | 'done';

interface OrchestrationState {
  models: ModelsResponse | null;
  selectedModel: string | null;
  demoCase: DemoCaseResponse | null;
  backendAvailable: boolean;

  errorLog: string;
  specExcerpt: string;
  designImageB64: string;
  testedImageB64: string;
  errorLogFile: UploadedFileInput | null;
  designImageFile: UploadedFileInput | null;
  testedImageFile: UploadedFileInput | null;
  specFiles: UploadedFileInput[];
  designReferenceFiles: UploadedFileInput[];

  isRunning: boolean;
  agentStatuses: AgentStatus[];
  revealedAgents: number;
  currentAgentName: string;

  result: OrchestrationResponse | null;
  isSampleResult: boolean;
  photoInspection: PCBDetectionResponse | null;
  error: string | null;

  highlightedBoxLabel: string | null;
  highlightedSpecIdx: number | null;
  expandedAgentIdx: number | null;
  inputCollapsed: boolean;

  fetchModels: () => Promise<void>;
  fetchDemoCase: () => Promise<void>;
  loadDemo: () => void;
  setErrorLog: (v: string) => void;
  setSpecExcerpt: (v: string) => void;
  setDesignImage: (b64: string) => void;
  setTestedImage: (b64: string) => void;
  setErrorLogFile: (f: UploadedFileInput | null) => void;
  setDesignImageFile: (f: UploadedFileInput | null) => void;
  setTestedImageFile: (f: UploadedFileInput | null) => void;
  addSpecFile: (f: UploadedFileInput) => void;
  removeSpecFile: (fileId: string) => void;
  addDesignReferenceFile: (f: UploadedFileInput) => void;
  removeDesignReferenceFile: (fileId: string) => void;
  runDemo: () => Promise<void>;
  runCustom: () => Promise<void>;
  setHighlightedBoxLabel: (label: string | null) => void;
  setHighlightedSpecIdx: (idx: number | null) => void;
  setExpandedAgentIdx: (idx: number | null) => void;
  setInputCollapsed: (v: boolean) => void;
  reset: () => void;
}

export const AGENT_NAMES = [
  'Error Analyzer',
  'Spec Checker',
  'CAD Mapper',
  'Defect Inspector',
  'Spec Resolution',
];

const PREFERRED_MODEL = 'gemini-3.8-flash';

const INITIAL_STATUSES: AgentStatus[] = ['idle', 'idle', 'idle', 'idle', 'idle'];

function statusesForProgress(stage: string): Partial<OrchestrationState> {
  const stages: Record<string, Partial<OrchestrationState>> = {
    starting: { currentAgentName: 'Preparing inspection' },
    preparing: { currentAgentName: 'Reading uploaded evidence' },
    fallback: { currentAgentName: 'Primary model timed out — switching remaining agents to the alternate model' },
    symptom: {
      agentStatuses: ['running', 'idle', 'idle', 'idle', 'idle'],
      revealedAgents: 1,
      currentAgentName: AGENT_NAMES[0],
    },
    spec_design: {
      agentStatuses: ['done', 'running', 'running', 'idle', 'idle'],
      revealedAgents: 3,
      currentAgentName: 'Spec Checker + CAD Mapper',
    },
    physical: {
      agentStatuses: ['done', 'done', 'done', 'running', 'idle'],
      revealedAgents: 4,
      currentAgentName: AGENT_NAMES[3],
    },
    resolution: {
      agentStatuses: ['done', 'done', 'done', 'done', 'running'],
      revealedAgents: 5,
      currentAgentName: AGENT_NAMES[4],
    },
  };
  return stages[stage] ?? {};
}

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

export const useOrchestrationStore = create<OrchestrationState>((set, get) => ({
  models: null,
  selectedModel: null,
  demoCase: null,
  backendAvailable: false,
  errorLog: '',
  specExcerpt: '',
  designImageB64: '',
  testedImageB64: '',
  errorLogFile: null,
  designImageFile: null,
  testedImageFile: null,
  specFiles: [],
  designReferenceFiles: [],
  isRunning: false,
  agentStatuses: [...INITIAL_STATUSES],
  revealedAgents: 0,
  currentAgentName: '',
  result: null,
  isSampleResult: false,
  photoInspection: null,
  error: null,
  highlightedBoxLabel: null,
  highlightedSpecIdx: null,
  expandedAgentIdx: null,
  inputCollapsed: false,

  fetchModels: async () => {
    try {
      const health = await api.health();
      if (health.status !== 'ok') throw new Error('Inspection API is unavailable');
      set(() => ({ backendAvailable: true }));
    } catch {
      set(() => ({ backendAvailable: false }));
      return;
    }
    try {
      const all = await api.models();
      const supported = all.available_models.filter((m) => m.name === PREFERRED_MODEL || /gemma-?4/i.test(m.name));
      const models = { ...all, available_models: supported };
      const selected = supported.find((m) => m.name === PREFERRED_MODEL)?.name
        ?? supported.find((m) => m.name === all.recommended_model)?.name
        ?? supported[0]?.name
        ?? null;
      set(() => ({ models: { ...models, recommended_model: selected ?? '' }, selectedModel: selected, backendAvailable: true }));
    } catch { set(() => ({ models: null, selectedModel: null })); }
  },

  fetchDemoCase: async () => {
    try {
      const demoCase = await api.demoCase();
      set(() => ({ demoCase }));
    } catch { /* non-critical */ }
  },

  loadDemo: () => {
    const dc = get().demoCase;
    if (dc) {
      set(() => ({
        errorLog: dc.request.input.error_log,
        specExcerpt: dc.request.input.spec_excerpt ?? '',
        designImageB64: '',
        testedImageB64: '',
        errorLogFile: null,
        designImageFile: null,
        testedImageFile: null,
        specFiles: [],
        designReferenceFiles: [],
      }));
    } else {
      set(() => ({
        errorLog: DEMO_INPUT.errorLog,
        specExcerpt: DEMO_INPUT.specExcerpt,
        designImageB64: '',
        testedImageB64: '',
        errorLogFile: null,
        designImageFile: null,
        testedImageFile: null,
        specFiles: [],
        designReferenceFiles: [],
      }));
    }
  },

  setErrorLog: (v) => set(() => ({ errorLog: v })),
  setSpecExcerpt: (v) => set(() => ({ specExcerpt: v })),
  setDesignImage: (b64) => set(() => ({ designImageB64: b64 })),
  setTestedImage: (b64) => set(() => ({ testedImageB64: b64 })),
  setErrorLogFile: (f) => set(() => ({ errorLogFile: f })),
  setDesignImageFile: (f) => set(() => ({ designImageFile: f })),
  setTestedImageFile: (f) => set(() => ({ testedImageFile: f })),
  addSpecFile: (f) => set((state) => ({ specFiles: [...state.specFiles, f] })),
  removeSpecFile: (fileId) => set((state) => ({
    specFiles: state.specFiles.filter((file) => file.file_id !== fileId),
  })),
  addDesignReferenceFile: (f) => set((state) => ({ designReferenceFiles: [...state.designReferenceFiles, f] })),
  removeDesignReferenceFile: (fileId) => set((state) => ({
    designReferenceFiles: state.designReferenceFiles.filter((file) => file.file_id !== fileId),
  })),
  setHighlightedBoxLabel: (label) => set(() => ({ highlightedBoxLabel: label })),
  setHighlightedSpecIdx: (idx) => set(() => ({ highlightedSpecIdx: idx })),
  setExpandedAgentIdx: (idx) => set(() => ({ expandedAgentIdx: idx })),
  setInputCollapsed: (v) => set(() => ({ inputCollapsed: v })),

  runDemo: async () => {
    const result = buildDemoResponse();
    set(() => ({
      isRunning: false, error: null, result, isSampleResult: true,
      agentStatuses: ['done', 'done', 'done', 'done', 'done'],
      revealedAgents: 5, currentAgentName: 'Sample report',
      highlightedBoxLabel: null, highlightedSpecIdx: null, expandedAgentIdx: null,
      inputCollapsed: true,
    }));
  },

  runCustom: async () => {
    const s = get();
    if (!s.backendAvailable) {
      set(() => ({ error: 'Inspection server is unavailable. Start the backend, then try again.' }));
      return;
    }
    const designImage = s.designImageFile
      ? { mime_type: s.designImageFile.mime_type, base64_data: s.designImageFile.base64_data }
      : s.designImageB64
        ? { mime_type: 'image/png', base64_data: s.designImageB64 }
        : null;
    const testedImage = s.testedImageFile
      ? { mime_type: s.testedImageFile.mime_type, base64_data: s.testedImageFile.base64_data }
      : s.testedImageB64
        ? { mime_type: 'image/png', base64_data: s.testedImageB64 }
        : null;

    const photoOnly = !designImage || !testedImage;
    const singlePhoto = testedImage ?? designImage;
    const referenceImage = designImage ?? singlePhoto;
    const boardPhoto = testedImage ?? singlePhoto;

    if (!singlePhoto || !referenceImage || !boardPhoto) {
      set(() => ({
        error: 'Upload a clear photo of the PCB to inspect it.',
      }));
      return;
    }

    const hasUploadedBundle = Boolean(
      s.errorLogFile && s.designImageFile && s.testedImageFile && s.specFiles.length > 0,
    );

    set(() => ({
      isRunning: true, error: null, result: null, isSampleResult: false, photoInspection: null,
      agentStatuses: [...INITIAL_STATUSES],
      revealedAgents: 0, currentAgentName: 'Preparing inspection',
      highlightedBoxLabel: null, highlightedSpecIdx: null, expandedAgentIdx: null,
      inputCollapsed: true,
    }));

    const runId = crypto.randomUUID();
    let keepPolling = true;
    const pollProgress = async () => {
      while (keepPolling) {
        try {
          const { stage } = await api.orchestrationProgress(runId);
          const progress = statusesForProgress(stage);
          if (Object.keys(progress).length) set(() => progress);
        } catch { /* The POST request remains authoritative if polling is unavailable. */ }
        if (keepPolling) await wait(800);
      }
    };
    const progressPoller = pollProgress();

    try {
      let result: OrchestrationResponse;
      if (hasUploadedBundle) {
        result = await api.orchestrateUploaded({
          input: {
            error_log_file: s.errorLogFile!,
            design_image_file: s.designImageFile!,
            tested_image_file: s.testedImageFile!,
            spec_files: s.specFiles,
            design_reference_files: s.designReferenceFiles,
          },
          options: { model: s.selectedModel ?? undefined, include_raw_agent_payloads: true },
        }, runId);
      } else {
        result = await api.orchestrate({
          input: {
            error_log: s.errorLog.trim() || (photoOnly
              ? 'Photo-only PCB inspection. Report only visible anomalies; do not infer electrical failures or unobserved defects.'
              : 'No error log supplied. Inspect the tested PCB for visible manufacturing defects relative to the design image.'),
            spec_excerpt: s.specExcerpt.trim() || (photoOnly
              ? 'No board-specific specification or reference image was supplied. Do not claim IPC compliance, measurements, or electrical test results. Assess visible evidence only and state uncertainty.'
              : 'No board-specific specification supplied. Mark specification compliance as not assessed.'),
            design_image: referenceImage,
            tested_image: boardPhoto,
          },
          options: { model: s.selectedModel ?? undefined, include_raw_agent_payloads: true },
        }, runId);
      }
      set(() => ({
        result,
        isRunning: false,
        agentStatuses: ['done', 'done', 'done', 'done', 'done'],
        revealedAgents: 5,
        currentAgentName: 'Inspection complete',
      }));
    } catch (e) {
      set(() => ({
        isRunning: false,
        error: e instanceof Error ? e.message : String(e),
        agentStatuses: [...INITIAL_STATUSES],
      }));
    } finally {
      keepPolling = false;
      await progressPoller;
    }
  },

  reset: () => set(() => ({
    errorLog: '',
    specExcerpt: '',
    designImageB64: '',
    testedImageB64: '',
    errorLogFile: null,
    designImageFile: null,
    testedImageFile: null,
    specFiles: [],
    designReferenceFiles: [],
    isRunning: false,
    agentStatuses: [...INITIAL_STATUSES],
    revealedAgents: 0,
    currentAgentName: '',
    result: null,
    isSampleResult: false,
    photoInspection: null,
    error: null,
    highlightedBoxLabel: null,
    highlightedSpecIdx: null,
    expandedAgentIdx: null,
    inputCollapsed: false,
  })),
}));
