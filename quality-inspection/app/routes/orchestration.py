from __future__ import annotations

import base64

from fastapi import APIRouter, Header, HTTPException

from ..config import get_settings
from ..demo_data import load_demo_case
from ..file_processing import (
    DemoRunOptions,
    UploadedOrchestrationRequest,
    _build_grouped_case_mappings,
    _build_spec_navigation_bundle,
    _decode_uploaded_text,
    _plain_excerpts_from_uploaded_files,
)
from ..schemas import (
    GroupedCaseResult,
    GroupedOrchestrationRequest,
    GroupedOrchestrationResponse,
    ImageInput,
    OrchestrationInput,
    OrchestrationOptions,
    OrchestrationRequest,
    OrchestrationResponse,
)
from ..run_progress import get_run_stage, set_run_stage

router = APIRouter(tags=["orchestration"])


def _get_engine():
    from ..main import get_engine
    return get_engine()


def _progress_callback(run_id: str | None):
    return lambda stage: set_run_stage(run_id, stage)


@router.get("/orchestrate/progress/{run_id}")
def orchestration_progress(run_id: str) -> dict[str, str]:
    return {"stage": get_run_stage(run_id)}


@router.post("/orchestrate", response_model=OrchestrationResponse)
def orchestrate(
    request: OrchestrationRequest,
    run_id: str | None = Header(default=None, alias="X-Run-ID"),
) -> OrchestrationResponse:
    set_run_stage(run_id, "starting")
    try:
        engine = _get_engine()
        return engine.run(request, progress=_progress_callback(run_id))
    except HTTPException:
        set_run_stage(run_id, "error")
        raise
    except ValueError as exc:
        set_run_stage(run_id, "error")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        set_run_stage(run_id, "error")
        raise HTTPException(status_code=502, detail=f"Orchestration failed (Gemini upstream): {exc}") from exc


@router.post("/orchestrate/uploaded", response_model=OrchestrationResponse)
def orchestrate_uploaded(
    payload: UploadedOrchestrationRequest,
    run_id: str | None = Header(default=None, alias="X-Run-ID"),
) -> OrchestrationResponse:
    set_run_stage(run_id, "preparing")
    try:
        engine = _get_engine()
        error_log = _decode_uploaded_text(payload.input.error_log_file).strip()
        if not error_log:
            raise ValueError("Uploaded .log file is empty")

        spec_inputs = payload.input.spec_files[:]
        if payload.input.spec_file and payload.input.spec_file not in spec_inputs:
            spec_inputs.append(payload.input.spec_file)
        if not spec_inputs:
            raise ValueError("No uploaded spec file supplied.")

        spec_excerpt, spec_focus_plan, spec_reference_images = _build_spec_navigation_bundle(
            spec_inputs,
            error_log=error_log,
        )
        design_reference_text = _plain_excerpts_from_uploaded_files(
            payload.input.design_reference_files,
        )
        design_reference_text = design_reference_text.strip() or None

        request = OrchestrationRequest(
            input=OrchestrationInput(
                error_log=error_log,
                spec_excerpt=spec_excerpt,
                spec_focus_plan=spec_focus_plan,
                spec_image_parts=[
                    ImageInput(
                        mime_type=mime_type,
                        base64_data=base64.b64encode(image_bytes).decode("ascii"),
                    )
                    for image_bytes, mime_type in spec_reference_images
                ],
                design_reference_text=design_reference_text,
                design_image=ImageInput(
                    mime_type=payload.input.design_image_file.mime_type,
                    base64_data=payload.input.design_image_file.base64_data,
                ),
                tested_image=ImageInput(
                    mime_type=payload.input.tested_image_file.mime_type,
                    base64_data=payload.input.tested_image_file.base64_data,
                ),
                background_context=payload.input.background_context,
                todo_context=payload.input.todo_context,
                example_context=payload.input.example_context,
            ),
            options=payload.options,
        )
        return engine.run(request, progress=_progress_callback(run_id))
    except HTTPException:
        set_run_stage(run_id, "error")
        raise
    except ValueError as exc:
        set_run_stage(run_id, "error")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        set_run_stage(run_id, "error")
        raise HTTPException(status_code=502, detail=f"Uploaded orchestration failed: {exc}") from exc


@router.post("/orchestrate/grouped/preview")
def orchestrate_grouped_preview(payload: GroupedOrchestrationRequest) -> dict:
    try:
        mappings = _build_grouped_case_mappings(
            error_logs=payload.input.error_logs,
            design_images=payload.input.design_images,
            tested_images=payload.input.tested_images,
            spec_excerpts=payload.input.spec_excerpts,
            spec_document_paths=payload.input.spec_document_paths,
            strict=payload.options.strict_index_pairing,
        )
        return {
            "total_cases": len(mappings),
            "strict_index_pairing": payload.options.strict_index_pairing,
            "input_counts": {
                "error_logs": len(payload.input.error_logs),
                "design_images": len(payload.input.design_images),
                "tested_images": len(payload.input.tested_images),
                "spec_excerpts": len(payload.input.spec_excerpts),
                "spec_document_paths": len(payload.input.spec_document_paths),
            },
            "mappings": [row.model_dump() for row in mappings],
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orchestrate/grouped", response_model=GroupedOrchestrationResponse)
def orchestrate_grouped(request: GroupedOrchestrationRequest) -> GroupedOrchestrationResponse:
    engine = _get_engine()
    try:
        mappings = _build_grouped_case_mappings(
            error_logs=request.input.error_logs,
            design_images=request.input.design_images,
            tested_images=request.input.tested_images,
            spec_excerpts=request.input.spec_excerpts,
            spec_document_paths=request.input.spec_document_paths,
            strict=request.options.strict_index_pairing,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rows: list[GroupedCaseResult] = []
    success = 0
    for mapping in mappings:
        try:
            error_log = request.input.error_logs[mapping.error_log_index]
            design_image = request.input.design_images[mapping.design_image_index]
            tested_image = request.input.tested_images[mapping.tested_image_index]

            spec_excerpt = None
            spec_document_path = None
            if mapping.spec_source_type == "spec_excerpt":
                spec_excerpt = request.input.spec_excerpts[mapping.spec_source_index]
            else:
                spec_document_path = request.input.spec_document_paths[mapping.spec_source_index]

            run_request = OrchestrationRequest(
                input=OrchestrationInput(
                    error_log=error_log,
                    spec_excerpt=spec_excerpt,
                    spec_document_path=spec_document_path,
                    design_image=design_image,
                    tested_image=tested_image,
                    background_context=request.input.background_context,
                    todo_context=request.input.todo_context,
                    example_context=request.input.example_context,
                ),
                options=OrchestrationOptions(
                    model=request.options.model,
                    include_raw_agent_payloads=request.options.include_raw_agent_payloads,
                ),
            )

            run_response = engine.run(run_request)
            success += 1
            rows.append(
                GroupedCaseResult(
                    case_index=mapping.case_index,
                    mapping=mapping,
                    status="ok",
                    run_id=run_response.run_id,
                    model_used=run_response.model_used,
                    latency_sec=(run_response.ended_at - run_response.started_at).total_seconds(),
                    result=run_response,
                )
            )
        except Exception as exc:
            rows.append(
                GroupedCaseResult(
                    case_index=mapping.case_index,
                    mapping=mapping,
                    status="error",
                    error=str(exc),
                )
            )

    return GroupedOrchestrationResponse(
        total_cases=len(rows),
        success_cases=success,
        failed_cases=len(rows) - success,
        cases=rows,
    )


@router.post("/orchestrate/demo", response_model=OrchestrationResponse)
def orchestrate_demo(options: DemoRunOptions | None = None) -> OrchestrationResponse:
    engine = _get_engine()
    demo = load_demo_case(get_settings())
    options = options or DemoRunOptions()

    request = demo.request.model_copy(deep=True)
    request.options.model = options.model
    request.options.include_raw_agent_payloads = options.include_raw_agent_payloads

    try:
        return engine.run(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Demo orchestration failed (Gemini upstream): {exc}") from exc
