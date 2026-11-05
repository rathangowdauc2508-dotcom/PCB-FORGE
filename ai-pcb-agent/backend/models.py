"""
Core Pydantic models shared across the AI PCB Manufacturing Agent backend.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
import uuid


def gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


# ---------------------------------------------------------------------------
# PCB
# ---------------------------------------------------------------------------

class PCBAnalysis(BaseModel):
    board_width_mm: Optional[float] = None
    board_height_mm: Optional[float] = None
    area_mm2: Optional[float] = None
    layers: int
    components: int
    footprints: int
    pads: int
    vias: int
    tracks: int
    zones: int
    min_trace_width_mm: Optional[float] = None
    min_clearance_mm: Optional[float] = None
    min_drill_diameter_mm: Optional[float] = None
    board_edge_clearance_mm: Optional[float] = None
    source: str = Field(description="'pcbnew' | 'fallback_parser' | 'demo_fixture'")


class PCBProject(BaseModel):
    id: str
    filename: str
    uploaded_at: datetime
    analysis: Optional[PCBAnalysis] = None
    raw_path: Optional[str] = None


# ---------------------------------------------------------------------------
# DFM
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DFMStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class DFMIssue(BaseModel):
    type: str
    severity: Severity
    actual: float
    required: float
    message: str


class DFMCheck(BaseModel):
    name: str
    passed: Optional[bool] = None


class DFMResult(BaseModel):
    status: DFMStatus
    total_checks: int
    passed_checks: int
    issues: List[DFMIssue]
    checks: List[DFMCheck]
    ai_summary: Optional[str] = None
    ai_evidence: List[dict] = Field(default_factory=list)
    ai_status: str = "unavailable"


# ---------------------------------------------------------------------------
# BOM
# ---------------------------------------------------------------------------

class Availability(str, Enum):
    AVAILABLE = "AVAILABLE"
    LOW_STOCK = "LOW_STOCK"
    UNAVAILABLE = "UNAVAILABLE"


class BOMItem(BaseModel):
    part: str
    description: str
    quantity: int
    unit_cost_usd: float
    availability: Availability
    alternatives: List[str] = []


class BOMResult(BaseModel):
    items: List[BOMItem]
    total_cost_usd: float
    risk_count: int
    ai_summary: Optional[str] = None
    ai_evidence: List[dict] = Field(default_factory=list)
    ai_status: str = "unavailable"


# ---------------------------------------------------------------------------
# Manufacturing
# ---------------------------------------------------------------------------

class Manufacturer(BaseModel):
    id: str
    name: str
    base_price_usd: float
    lead_time_days: int
    max_layers: int
    min_trace_width_mm: float
    min_clearance_mm: float
    min_drill_diameter_mm: float
    rating: float


class ManufacturingQuote(BaseModel):
    manufacturer_id: str
    manufacturer_name: str
    price_usd: float
    lead_time_days: int
    dfm_compatible: Optional[bool] = None
    layer_compatible: bool
    score: float
    reasons: List[str]


class ManufacturingRecommendation(BaseModel):
    recommended: ManufacturingQuote
    all_quotes: List[ManufacturingQuote]
    explanation: str
    ai_status: str = "unavailable"


# ---------------------------------------------------------------------------
# Manufacturing requests
# ---------------------------------------------------------------------------

class OrderStatus(str, Enum):
    REQUESTED = "REQUESTED"
    QUOTED = "QUOTED"
    FAILED = "FAILED"


class OrderCreateRequest(BaseModel):
    pcb_id: str
    manufacturer_id: str
    quantity: int = Field(gt=0, le=1000)
    total_price: float


class Order(BaseModel):
    id: str
    pcb_id: str
    manufacturer_id: str
    manufacturer_name: str
    quantity: int
    total_price: float
    estimated_delivery_days: int
    status: OrderStatus
    created_at: datetime


class AgentEvent(BaseModel):
    id: str
    project_id: str
    agent: str
    icon: str
    message: str
    status: str  # "running" | "done" | "error"
    timestamp: datetime
