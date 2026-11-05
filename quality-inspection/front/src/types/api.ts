export interface BoundingBox {
  label: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  confidence: number;
}

export interface AgentTrace {
  agent_id: string;
  agent_name: string;
  model_used?: string | null;
  handoff_to: string | null;
  handoff_message: string | null;
  output: Record<string, unknown>;
}

export interface FinalOutput {
  root_cause: string;
  impact: string;
  resolution: string[];
  confidence: number;
  bounding_boxes: BoundingBox[];
}

export interface OrchestrationResponse {
  run_id: string;
  model_used: string;
  started_at: string;
  ended_at: string;
  input: Record<string, unknown>;
  output: FinalOutput;
  agent_trace: AgentTrace[];
  annotated_tested_image?: string | null;
}

export interface PCBDetectionResponse {
  model_name: string;
  model_weights: string;
  image_width: number;
  image_height: number;
  inference_ms: number;
  annotated_image_base64: string;
  detections: {
    id: number;
    class_name: string;
    confidence: number;
    bbox: { x1: number; y1: number; x2: number; y2: number };
  }[];
}

export interface LegacyPhotoInspectionResponse {
  summary?: string;
  findings?: Array<{
    defect?: string;
    severity?: string;
    visual_evidence?: string;
    recommendation?: string;
    confidence?: number;
  }>;
}

export interface ImageInput {
  mime_type: string;
  base64_data?: string | null;
  file_path?: string | null;
}

export interface OrchestrationInput {
  error_log: string;
  spec_excerpt?: string | null;
  spec_document_path?: string | null;
  design_reference_text?: string | null;
  design_image: ImageInput;
  tested_image: ImageInput;
  background_context?: string | null;
  todo_context?: string | null;
  example_context?: string | null;
}

export interface OrchestrationOptions {
  model?: string | null;
  include_raw_agent_payloads: boolean;
}

export interface OrchestrationRequest {
  input: OrchestrationInput;
  options: OrchestrationOptions;
}

export interface UploadedFileInput {
  file_name: string;
  mime_type: string;
  base64_data: string;
  file_id?: string;
}

export interface UploadedOrchestrationInput {
  error_log_file: UploadedFileInput;
  design_image_file: UploadedFileInput;
  tested_image_file: UploadedFileInput;
  spec_files: UploadedFileInput[];
  design_reference_files: UploadedFileInput[];
  background_context?: string | null;
  todo_context?: string | null;
  example_context?: string | null;
}

export interface UploadedOrchestrationRequest {
  input: UploadedOrchestrationInput;
  options: OrchestrationOptions;
}

export interface ModelInfo {
  name: string;
  display_name: string | null;
  supported_actions: string[];
}

export interface ModelsResponse {
  recommended_model: string;
  available_models: ModelInfo[];
}

export interface DemoCaseResponse {
  request: OrchestrationRequest;
  expected_output_example: Record<string, unknown>;
}

// Agent-specific output types
export interface SuspectPart {
  part_name: string;
  likely_fault_mode: string;
  why_related: string;
  confidence: number;
}

export interface SymptomOutput {
  error_interpretation: string;
  suspect_parts: SuspectPart[];
  handoff_message: string;
}

export interface SpecWatchItem {
  rule_id: string;
  what_to_check: string;
  why_relevant: string;
  priority: string;
}

export interface SpecOutput {
  spec_watchlist: SpecWatchItem[];
  spec_risk_summary: string;
  handoff_message: string;
}

export interface CadMapping {
  part_name: string;
  schematic_reference: string;
  reason: string;
  bbox: { x1: number; y1: number; x2: number; y2: number };
}

export interface DesignOutput {
  cad_mappings: CadMapping[];
  handoff_message: string;
}

export interface DefectVerification {
  part_name: string;
  defect_type: string;
  bbox: { x1: number; y1: number; x2: number; y2: number };
  confidence: number;
  evidence: string;
  crop_note: string;
}

export interface PhysicalOutput {
  defect_verification: DefectVerification[];
  root_cause_candidate: string;
  impact: string;
  handoff_message: string;
}

export interface SpecCheck {
  rule_id: string;
  rule_text: string;
  compliance_status: string;
  gap: string;
}

export interface ResolutionOutput {
  spec_checks: SpecCheck[];
  final_root_cause: string;
  final_resolution: string[];
  final_confidence: number;
}

// PCB defect analysis types (matching backend app/schemas.py)

export interface DefectBoundingBox {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
}

export interface DetectedDefect {
  defect_type: string;
  description: string;
  severity: 'low' | 'medium' | 'high';
  bounding_box: DefectBoundingBox;
}

export interface AnalysisResult {
  defects: DetectedDefect[];
  total_defects: number;
  template_image: string;
  annotated_image: string;
  diff_summary: string;
}

export interface TemplateStatus {
  exists: boolean;
  image: string | null;
}
