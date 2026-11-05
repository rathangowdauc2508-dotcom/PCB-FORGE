from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ImageInput(BaseModel):
    mime_type: str = Field(default="image/png", description="MIME type of the image bytes")
    base64_data: str | None = Field(default=None, description="Raw base64 data without data-uri prefix")
    file_path: str | None = Field(default=None, description="Absolute or relative local file path")

    @model_validator(mode="after")
    def validate_source(self) -> "ImageInput":
        if not self.base64_data and not self.file_path:
            raise ValueError("Either base64_data or file_path must be provided")
        return self


class OrchestrationInput(BaseModel):
    error_log: str = Field(..., min_length=3)
    spec_excerpt: str | None = Field(default=None, min_length=3)
    design_reference_text: str | None = Field(default=None, min_length=3)
    spec_focus_plan: str | None = Field(
        default=None,
        min_length=3,
        description="Structured spec TOC + section focus plan generated from uploaded spec PDFs.",
    )
    spec_image_parts: list[ImageInput] = Field(
        default_factory=list,
        description="Optional rendered PDF page images for multimodal spec reasoning.",
    )
    spec_document_path: str | None = Field(
        default=None,
        description="Optional local path to PDF/TXT spec file. Used when spec_excerpt is not provided.",
    )
    design_image: ImageInput
    tested_image: ImageInput
    background_context: str | None = None
    todo_context: str | None = None
    example_context: str | None = None

    @model_validator(mode="after")
    def validate_spec_source(self) -> "OrchestrationInput":
        if not self.spec_excerpt and not self.spec_document_path:
            raise ValueError("Either spec_excerpt or spec_document_path must be provided")
        return self


class OrchestrationOptions(BaseModel):
    model: str | None = None
    include_raw_agent_payloads: bool = True


class OrchestrationRequest(BaseModel):
    input: OrchestrationInput
    options: OrchestrationOptions = Field(default_factory=OrchestrationOptions)


class GroupedInputBundle(BaseModel):
    error_logs: list[str] = Field(default_factory=list, description="Error logs to analyze")
    design_images: list[ImageInput] = Field(default_factory=list, description="GT/CAD/template circuit images")
    tested_images: list[ImageInput] = Field(default_factory=list, description="Defect/physical circuit images")
    spec_excerpts: list[str] = Field(default_factory=list, description="Optional per-case spec excerpts")
    spec_document_paths: list[str] = Field(default_factory=list, description="Optional per-case spec document paths")
    background_context: str | None = None
    todo_context: str | None = None
    example_context: str | None = None

    @model_validator(mode="after")
    def validate_grouped_sources(self) -> "GroupedInputBundle":
        if not self.error_logs:
            raise ValueError("error_logs must include at least one item")
        if not self.design_images:
            raise ValueError("design_images must include at least one item")
        if not self.tested_images:
            raise ValueError("tested_images must include at least one item")
        if not self.spec_excerpts and not self.spec_document_paths:
            raise ValueError("Either spec_excerpts or spec_document_paths must include at least one item")
        return self


class GroupedOrchestrationOptions(BaseModel):
    model: str | None = None
    include_raw_agent_payloads: bool = True
    strict_index_pairing: bool = True


class GroupedOrchestrationRequest(BaseModel):
    input: GroupedInputBundle
    options: GroupedOrchestrationOptions = Field(default_factory=GroupedOrchestrationOptions)


class BoundingBox(BaseModel):
    label: str
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class AgentTrace(BaseModel):
    agent_id: str
    agent_name: str
    model_used: str | None = None
    handoff_to: str | None = None
    handoff_message: str | None = None
    output: dict[str, Any]


class FinalOutput(BaseModel):
    root_cause: str
    impact: str
    resolution: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_boxes: list[BoundingBox]


class OrchestrationResponse(BaseModel):
    run_id: str
    model_used: str
    started_at: datetime
    ended_at: datetime
    input: dict[str, Any]
    output: FinalOutput
    agent_trace: list[AgentTrace]
    annotated_tested_image: str | None = Field(
        default=None,
        description="Base64 PNG of the tested board with bounding boxes and labels drawn by Pillow.",
    )


class GroupedCasePreview(BaseModel):
    case_index: int
    error_log_index: int
    design_image_index: int
    tested_image_index: int
    spec_source_type: str
    spec_source_index: int


class GroupedCaseResult(BaseModel):
    case_index: int
    mapping: GroupedCasePreview
    status: str
    run_id: str | None = None
    model_used: str | None = None
    latency_sec: float | None = None
    error: str | None = None
    result: OrchestrationResponse | None = None


class GroupedOrchestrationResponse(BaseModel):
    total_cases: int
    success_cases: int
    failed_cases: int
    cases: list[GroupedCaseResult]


class ModelInfo(BaseModel):
    name: str
    display_name: str | None = None
    supported_actions: list[str] = Field(default_factory=list)


class ModelsResponse(BaseModel):
    recommended_model: str
    available_models: list[ModelInfo]


class DemoCaseResponse(BaseModel):
    request: OrchestrationRequest
    expected_output_example: dict[str, Any]


class VisionProbeResponse(BaseModel):
    probed_at: datetime
    candidate_models: list[str]
    results: list[dict[str, Any]]


class KeyPoolStatusResponse(BaseModel):
    key_count: int
    keys: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# PCB defect analysis models (ported from pcb-analysis/backend/src/models.py)
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DefectBoundingBox(BaseModel):
    """Pixel-coordinate bounding box for defect regions.

    Separate from :class:`BoundingBox` which uses ``x1/y1`` style for
    orchestration overlay rendering.
    """
    x_min: int = Field(description="Left edge in pixels")
    y_min: int = Field(description="Top edge in pixels")
    x_max: int = Field(description="Right edge in pixels")
    y_max: int = Field(description="Bottom edge in pixels")


class GeminiDefectResponse(BaseModel):
    defect_type: str = Field(description="Type of defect detected")
    description: str = Field(description="Description of the defect")
    severity: Severity = Field(description="Severity level")


class DetectedDefect(BaseModel):
    defect_type: str = Field(description="Type of defect detected")
    description: str = Field(description="Description of the defect")
    severity: Severity = Field(description="Severity level")
    bounding_box: DefectBoundingBox = Field(description="Location in pixels")


class AnalysisResult(BaseModel):
    defects: list[DetectedDefect] = Field(default_factory=list)
    total_defects: int = Field(default=0, description="Total number of defects found")
    template_image: str = Field(default="", description="Base64 reference template PNG")
    annotated_image: str = Field(default="", description="Base64 annotated PNG")
    diff_summary: str = Field(default="", description="Summary of diff analysis")
