export interface PCBAnalysis {
  board_width_mm: number | null;
  board_height_mm: number | null;
  area_mm2: number | null;
  layers: number;
  components: number;
  footprints: number;
  pads: number;
  vias: number;
  tracks: number;
  zones: number;
  min_trace_width_mm: number | null;
  min_clearance_mm: number | null;
  min_drill_diameter_mm: number | null;
  board_edge_clearance_mm: number | null;
  source: string;
}

export type Severity = "LOW" | "MEDIUM" | "HIGH";
export type DFMStatus = "PASS" | "WARNING" | "FAIL";

export interface EvidenceReference {
  id: string;
  label: string;
  detail: string;
}

export interface DFMIssue {
  type: string;
  severity: Severity;
  actual: number;
  required: number;
  message: string;
}

export interface DFMCheck {
  name: string;
  passed: boolean | null;
}

export interface DFMResult {
  status: DFMStatus;
  total_checks: number;
  passed_checks: number;
  issues: DFMIssue[];
  checks: DFMCheck[];
  ai_summary?: string;
  ai_evidence?: EvidenceReference[];
  ai_status: "available" | "unavailable";
}

export type Availability = "AVAILABLE" | "LOW_STOCK" | "UNAVAILABLE";

export interface BOMItem {
  part: string;
  description: string;
  quantity: number;
  unit_cost_usd: number;
  availability: Availability;
  alternatives: string[];
}

export interface BOMResult {
  items: BOMItem[];
  total_cost_usd: number;
  risk_count: number;
  ai_summary?: string;
  ai_evidence?: EvidenceReference[];
  ai_status: "available" | "unavailable";
}

export interface ManufacturingQuote {
  manufacturer_id: string;
  manufacturer_name: string;
  price_usd: number;
  lead_time_days: number;
  dfm_compatible: boolean | null;
  layer_compatible: boolean;
  score: number;
  reasons: string[];
}

export interface ManufacturingRecommendation {
  recommended: ManufacturingQuote;
  all_quotes: ManufacturingQuote[];
  explanation: string;
  ai_status: "available" | "unavailable";
}

export interface AgentEvent {
  id: string;
  project_id: string;
  agent: string;
  icon: string;
  message: string;
  status: "running" | "done" | "error";
  timestamp: string;
}

export interface PaymentCheckoutSession {
  order_id: string; razorpay_order_id: string; key_id: string; amount: number; currency: string;
  manufacturer: string; quantity: number; total_price: number; estimated_delivery_days: number;
  payment_mode: "TEST";
}

export interface OrderResult {
  status: string; order_id: string; manufacturer: string; quantity: number; total_price: number;
  estimated_delivery_days: number; payment_id?: string; payment_mode?: "TEST" | "NOT_CHARGED"; currency?: string;
}

export interface AnalysisBundle {
  pcb_analysis: PCBAnalysis;
  dfm_result: DFMResult;
  bom_result: BOMResult;
  recommendation: ManufacturingRecommendation;
}

export interface HardwareInspectionResult {
  run_id: string;
  model_used: string;
  output: {
    root_cause: string;
    impact: string;
    resolution: string[];
    confidence: number;
    bounding_boxes: Array<{ label: string; x1: number; y1: number; x2: number; y2: number; confidence: number }>;
  };
  agent_trace: Array<{ agent_id: string; agent_name: string; handoff_message?: string | null; output: Record<string, unknown> }>;
  annotated_tested_image?: string | null;
}

export interface IntegratedBuildPlan {
  project_id: string;
  model_used: string;
  build_plan: {
    executive_summary: string;
    manufacturing_readiness: "READY" | "READY_WITH_ACTIONS" | "HOLD";
    design_risks: string[];
    quality_findings: string[];
    recommended_actions: Array<{ action: string; priority: "HIGH" | "MEDIUM" | "LOW"; reason: string }>;
    prototype_checklist: string[];
    confidence: number;
  };
}

export interface ProjectSummary {
  id: string;
  filename: string;
  uploaded_at: string;
  analyzed: boolean;
  inspected: boolean;
  has_build_plan: boolean;
  has_manufacturing_request: boolean;
}

export interface ProjectHistoryEntry {
  id: string;
  action: string;
  detail: string;
  created_at: string;
}

export interface ProjectComparison {
  baseline: { id: string; filename: string };
  current: { id: string; filename: string };
  metrics: Array<{ label: string; baseline: number; current: number; delta: number }>;
  dfm: { baseline: string | null; current: string | null; changed: boolean };
  bom: {
    baseline_cost_usd: number | null;
    current_cost_usd: number | null;
    cost_delta_usd: number;
    baseline_risks: number | null;
    current_risks: number | null;
  };
}


