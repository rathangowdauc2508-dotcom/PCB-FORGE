from __future__ import annotations

import shutil
import uuid
import io
import logging
import base64
import csv
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from pathlib import PurePosixPath

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from agents import orchestrator
import db

router = APIRouter(prefix="/api/pcb", tags=["pcb"])
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_PCB_UPLOAD_BYTES = 25 * 1024 * 1024


async def _store_board_revision(file: UploadFile, project_id: str, parent_revision_id: str | None = None) -> dict:
    """Validate and atomically store a KiCad board as an immutable revision."""
    raw_name = (file.filename or "").replace("\\", "/")
    filename = PurePosixPath(raw_name).name
    if not filename or PurePosixPath(filename).suffix.lower() != ".kicad_pcb":
        raise HTTPException(status_code=400, detail="Upload a KiCad .kicad_pcb board file.")

    storage_token = uuid.uuid4().hex
    staging_path = UPLOAD_DIR / f".{storage_token}.upload"
    dest = UPLOAD_DIR / f"{storage_token}.kicad_pcb"
    digest = hashlib.sha256()
    size = 0
    prefix = bytearray()
    try:
        with staging_path.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_PCB_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Board file exceeds the 25 MB upload limit.")
                digest.update(chunk)
                if len(prefix) < 4096:
                    prefix.extend(chunk[:4096 - len(prefix)])
                output.write(chunk)
        header = bytes(prefix).lstrip(b"\xef\xbb\xbf \t\r\n")
        if not size or not header.startswith(b"(kicad_pcb"):
            raise HTTPException(status_code=400, detail="The file does not look like a readable KiCad PCB board.")
        staging_path.replace(dest)
        created_at = datetime.now().astimezone().isoformat()
        revision = db.create_board_revision(
            project_id, filename, str(dest), digest.hexdigest(), size,
            created_at, parent_revision_id,
        )
        return revision
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    except ValueError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Could not store the uploaded board. Please try again.") from exc
    finally:
        staging_path.unlink(missing_ok=True)


@router.post("/upload")
async def upload_pcb(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    project_id = f"PCB-{uuid.uuid4().hex[:6].upper()}"
    created_at = datetime.now().astimezone().isoformat()
    db.PROJECTS[project_id] = {
        "id": project_id,
        "filename": PurePosixPath(file.filename.replace("\\", "/")).name,
        "uploaded_at": created_at,
    }
    db.EVENTS[project_id] = []
    db.save_project(db.PROJECTS[project_id])
    try:
        revision = await _store_board_revision(file, project_id)
    except Exception:
        db.delete_project(project_id)
        raise
    db.PROJECTS[project_id].update({
        "revision_id": revision["id"],
        "revision_number": revision["revision_number"],
        "source_sha256": revision["sha256"],
        "raw_path": revision["storage_path"],
    })
    db.save_project(db.PROJECTS[project_id])
    db.add_history(project_id, "uploaded", f"Uploaded {file.filename}")

    return {"id": project_id, "filename": revision["filename"], "revision_id": revision["id"],
            "revision_number": revision["revision_number"], "sha256": revision["sha256"]}


@router.post("/projects/{project_id}/revisions")
async def upload_revision(project_id: str, file: UploadFile = File(...)):
    project = db.PROJECTS.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="PCB project not found.")
    parent_revision_id = project.get("revision_id")
    revision = await _store_board_revision(file, project_id, parent_revision_id)
    # Keep the prior revision record intact; make the new source current and clear
    # current-view results so they cannot be mistaken for analysis of the new bytes.
    for key in ("pcb_analysis", "dfm_result", "bom_result", "recommendation", "physical_inspection", "build_plan"):
        project.pop(key, None)
    project.update({
        "filename": revision["filename"],
        "uploaded_at": revision["created_at"],
        "revision_id": revision["id"],
        "revision_number": revision["revision_number"],
        "source_sha256": revision["sha256"],
        "raw_path": revision["storage_path"],
    })
    db.save_project(project)
    db.add_history(project_id, "revision_uploaded", f"Added revision {revision['revision_number']} ({revision['sha256'][:12]}…)")
    return {key: revision[key] for key in ("id", "project_id", "revision_number", "filename", "sha256", "byte_size", "created_at", "parent_revision_id", "analysis_status")}


@router.get("/projects/{project_id}/revisions")
async def get_revisions(project_id: str):
    if project_id not in db.PROJECTS:
        raise HTTPException(status_code=404, detail="PCB project not found.")
    return [{key: revision[key] for key in ("id", "project_id", "revision_number", "filename", "sha256", "byte_size", "created_at", "parent_revision_id", "analysis_status", "tool_version")}
            for revision in db.list_board_revisions(project_id)]


@router.get("/projects/{project_id}/revisions/{revision_id}")
async def get_revision(project_id: str, revision_id: str):
    revision = db.get_board_revision(revision_id)
    if not revision or revision["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="Board revision not found.")
    revision.pop("storage_path", None)
    return revision

@router.get("/projects/{project_id}/revisions/{revision_id}/source")
async def get_revision_source(project_id: str, revision_id: str):
    revision = db.get_board_revision(revision_id)
    if not revision or revision["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="Board revision not found.")
    path = Path(revision["storage_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="The stored source file is unavailable.")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != revision["sha256"]:
        raise HTTPException(status_code=409, detail="Stored source integrity check failed.")
    return FileResponse(path, filename=revision["filename"], media_type="application/octet-stream")


@router.get("/projects")
async def list_projects():
    return [
        {
            "id": p["id"],
            "filename": p.get("filename", "PCB project"),
            "uploaded_at": p.get("uploaded_at"),
            "analyzed": "pcb_analysis" in p,
            "inspected": "physical_inspection" in p,
            "has_build_plan": p.get("build_plan") is not None,
            "has_manufacturing_request": bool(p.get("manufacturing_requests")),
        }
        for p in sorted(db.PROJECTS.values(), key=lambda row: row.get("uploaded_at", ""), reverse=True)
    ]


@router.delete("/projects/{project_id}")
async def delete_saved_project(project_id: str):
    if project_id not in db.PROJECTS:
        raise HTTPException(status_code=404, detail="Saved PCB project not found.")
    stored_paths = db.delete_project_workspace(project_id)
    allowed_roots = (UPLOAD_DIR.resolve(), (UPLOAD_DIR.parent / "knowledge").resolve())
    for raw_path in stored_paths:
        path = Path(raw_path).resolve()
        if any(path != root and root in path.parents for root in allowed_roots):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove deleted project file: %s", path)
    return {"deleted": project_id}


@router.get("/demo-board")
async def get_demo_board():
    sample = Path(__file__).resolve().parents[2] / "sample_data" / "robot_controller.kicad_pcb"
    if not sample.is_file():
        raise HTTPException(status_code=404, detail="Included demo board is missing from this installation.")
    return FileResponse(sample, filename=sample.name, media_type="application/octet-stream")


@router.get("/compare/{baseline_id}/{current_id}")
async def compare_projects(baseline_id: str, current_id: str):
    baseline = db.PROJECTS.get(baseline_id)
    current = db.PROJECTS.get(current_id)
    if not baseline or not current:
        raise HTTPException(status_code=404, detail="Both saved PCB projects must exist before comparing them.")
    if not baseline.get("pcb_analysis") or not current.get("pcb_analysis"):
        raise HTTPException(status_code=409, detail="Analyze both PCB projects before comparing revisions.")

    left = baseline["pcb_analysis"]
    right = current["pcb_analysis"]
    numeric_fields = (
        ("board_width_mm", "Board width (mm)"),
        ("board_height_mm", "Board height (mm)"),
        ("layers", "Layers"),
        ("components", "Components"),
        ("vias", "Vias"),
        ("tracks", "Tracks"),
        ("min_trace_width_mm", "Minimum trace width (mm)"),
        ("min_clearance_mm", "Minimum clearance (mm)"),
        ("min_drill_diameter_mm", "Minimum drill diameter (mm)"),
    )
    metrics = [
        {"label": label, "baseline": left.get(key), "current": right.get(key), "delta": round(right.get(key, 0) - left.get(key, 0), 4)}
        for key, label in numeric_fields
        if left.get(key) is not None and right.get(key) is not None
    ]
    old_bom = baseline.get("bom_result", {})
    new_bom = current.get("bom_result", {})
    old_dfm = baseline.get("dfm_result", {})
    new_dfm = current.get("dfm_result", {})
    return {
        "baseline": {"id": baseline_id, "filename": baseline.get("filename")},
        "current": {"id": current_id, "filename": current.get("filename")},
        "metrics": metrics,
        "dfm": {"baseline": old_dfm.get("status"), "current": new_dfm.get("status"), "changed": old_dfm.get("status") != new_dfm.get("status")},
        "bom": {
            "baseline_cost_usd": old_bom.get("total_cost_usd"),
            "current_cost_usd": new_bom.get("total_cost_usd"),
            "cost_delta_usd": round((new_bom.get("total_cost_usd", 0) or 0) - (old_bom.get("total_cost_usd", 0) or 0), 2),
            "baseline_risks": old_bom.get("risk_count"),
            "current_risks": new_bom.get("risk_count"),
        },
    }


@router.get("/{project_id}")
async def get_pcb(project_id: str):
    project = db.PROJECTS.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="PCB project not found.")
    return project


@router.get("/projects/{project_id}")
async def get_saved_project(project_id: str):
    project = db.PROJECTS.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="PCB project not found.")
    return project


@router.get("/{project_id}/manufacturing-package")
def download_manufacturing_package(project_id: str):
    """Create a traceable fabrication passport with board identity and review evidence."""
    project = db.PROJECTS.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="PCB project not found.")
    raw_path = Path(project.get("raw_path", ""))
    if not raw_path.is_file():
        raise HTTPException(status_code=404, detail="The uploaded KiCad board file is no longer available.")
    if "pcb_analysis" not in project:
        raise HTTPException(status_code=409, detail="Analyze this board before downloading its project package.")

    memory = io.BytesIO()
    export_notes: list[str] = []
    board_hash = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="pcb-forge-") as temp_dir:
        temp_path = Path(temp_dir)
        generated: list[Path] = []
        kicad_cli = shutil.which("kicad-cli")
        if not kicad_cli and os.name == "nt":
            install_roots = [Path(value) / "KiCad" for value in (os.getenv("ProgramFiles"), os.getenv("ProgramFiles(x86)")) if value]
            candidates = sorted((candidate for root in install_roots if root.is_dir() for candidate in root.glob("*/bin/kicad-cli.exe")), reverse=True)
            kicad_cli = str(candidates[0]) if candidates else None
        drc_summary: dict = {"status": "not_run", "reason": "KiCad CLI was not found on the backend machine."}
        drc_report: dict = {"status": "not_run", "message": "Install KiCad and make kicad-cli available to run the native KiCad design rule check."}
        if kicad_cli:
            (temp_path / "gerbers").mkdir()
            (temp_path / "drill").mkdir()
            (temp_path / "reports").mkdir()
            drc_path = temp_path / "reports" / "kicad-drc.json"
            try:
                drc_process = subprocess.run(
                    [kicad_cli, "pcb", "drc", "--format", "json", "--severity-all", "--exit-code-violations", "--output", str(drc_path), str(raw_path)],
                    capture_output=True, text=True, timeout=120,
                )
                if not drc_path.is_file():
                    raise RuntimeError(drc_process.stderr[-1000:] or "KiCad completed without creating its DRC report.")
                raw_drc = json.loads(drc_path.read_text(encoding="utf-8"))
                violations = raw_drc.get("violations", []) if isinstance(raw_drc, dict) else []
                unconnected = raw_drc.get("unconnected_items") if isinstance(raw_drc, dict) else None
                if not isinstance(violations, list) or not isinstance(unconnected, list):
                    raise RuntimeError("KiCad DRC report did not include its expected violations and unconnected-items lists.")
                drc_status = "passed" if drc_process.returncode == 0 and not violations and not unconnected else "issues_found"
                drc_report = {
                    "status": drc_status,
                    "return_code": drc_process.returncode,
                    "violation_count": len(violations) if isinstance(violations, list) else None,
                    "unconnected_count": len(unconnected) if isinstance(unconnected, list) else None,
                    "report": raw_drc,
                    "stderr": drc_process.stderr[-4000:],
                }
                drc_summary = {key: value for key, value in drc_report.items() if key != "report"}
                generated.append(drc_path)
                export_notes.append(f"KiCad native DRC: {drc_status}")
            except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError, RuntimeError) as exc:
                drc_report = {"status": "error", "message": str(exc)[:1000]}
                drc_summary = {"status": "error", "reason": str(exc)[:1000]}
                export_notes.append("KiCad native DRC: could not complete; see passport report.")
            for label, command in (
                ("gerbers", ["pcb", "export", "gerbers", "--output", str(temp_path / "gerbers") + os.sep, str(raw_path)]),
                ("drill files", ["pcb", "export", "drill", "--output", str(temp_path / "drill") + os.sep, str(raw_path)]),
            ):
                try:
                    subprocess.run([kicad_cli, *command], check=True, capture_output=True, text=True, timeout=90)
                    generated.extend(p for p in temp_path.rglob("*") if p.is_file() and p not in generated)
                    export_notes.append(f"KiCad {label}: generated")
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                    detail = getattr(exc, "stderr", "") or str(exc)
                    export_notes.append(f"KiCad {label}: export failed ({str(detail)[-500:]})")
        else:
            export_notes.append("KiCad CLI was not found; source board and review reports are included, but native DRC and Gerber/drill files were not generated.")

        pcb = project.get("pcb_analysis", {})
        dfm = project.get("dfm_result", {})
        bom = project.get("bom_result", {})
        recommendation = project.get("recommendation", {})
        dfm_status = str(dfm.get("status", "UNKNOWN")).upper().rsplit(".", 1)[-1]
        bom_risks = int(bom.get("risk_count", 0) or 0)
        gerbers_ready = "KiCad gerbers: generated" in export_notes
        drills_ready = "KiCad drill files: generated" in export_notes
        release_checks = [
            {"check": "KiCad native DRC", "status": "PASS" if drc_summary.get("status") == "passed" else "BLOCKED" if drc_summary.get("status") == "issues_found" else "NOT RUN"},
            {"check": "PCB Forge manufacturer DFM", "status": "PASS" if dfm_status == "PASS" else "BLOCKED" if dfm_status == "FAIL" else "REVIEW"},
            {"check": "Gerber export", "status": "PASS" if gerbers_ready else "NOT RUN"},
            {"check": "Drill export", "status": "PASS" if drills_ready else "NOT RUN"},
            {"check": "BOM sourcing risks", "status": "PASS" if bom_risks == 0 else "REVIEW"},
        ]
        if dfm_status == "FAIL" or drc_summary.get("status") == "issues_found":
            release_status = "HOLD"
        elif dfm_status != "PASS" or drc_summary.get("status") != "passed" or not gerbers_ready or not drills_ready or bom_risks > 0:
            release_status = "REVIEW REQUIRED"
        else:
            release_status = "RELEASE CANDIDATE"
        release_passport = {
            "product": "PCB Forge Fabrication Passport",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "project_id": project_id,
            "board_filename": project.get("filename"),
            "board_sha256": board_hash,
            "release_status": release_status,
            "release_checks": release_checks,
            "native_kicad_drc": drc_summary,
            "bom_sourcing_risk_count": bom_risks,
            "pcb_forge_manufacturer_dfm": {
                "status": dfm_status,
                "checks_passed": dfm.get("passed_checks"),
                "checks_total": dfm.get("total_checks"),
                "issues": dfm.get("issues", []),
            },
            "recommended_manufacturer": (recommendation.get("recommended") or {}).get("manufacturer_name"),
            "fabrication_exports": export_notes,
            "limits": [
                "A release candidate is a review aid, not a guarantee of fabrication success.",
                "PCB Forge manufacturer limits and supplier pricing are local planning data, not a live fabricator quote.",
                "Review the generated Gerber and drill files with the selected fabricator before ordering.",
            ],
        }
        inspection = project.get("physical_inspection")
        annotated_image = None
        if isinstance(inspection, dict):
            inspection = dict(inspection)
            annotated_image = inspection.pop("annotated_tested_image", None)
            inspection.pop("input", None)
        report = {
            "project_id": project_id,
            "filename": project.get("filename"),
            "uploaded_at": project.get("uploaded_at"),
            "pcb_analysis": pcb,
            "dfm_result": dfm,
            "bom_result": bom,
            "supplier_recommendation": recommendation,
            "physical_inspection": inspection,
            "build_plan": project.get("build_plan"),
            "manufacturing_requests": project.get("manufacturing_requests", []),
            "export_notes": export_notes,
            "release_passport": release_passport,
            "pricing_notice": "Supplier prices, availability, lead times, and unmatched-part costs are planning estimates, not live quotes.",
        }
        with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
            file_manifest: list[dict] = []

            def add_artifact(archive_path: str, content: bytes):
                archive.writestr(archive_path, content)
                file_manifest.append({"path": archive_path, "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})

            add_artifact(f"source/{raw_path.name}", raw_path.read_bytes())
            add_artifact("reports/project-report.json", json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8"))
            add_artifact("reports/dfm-report.json", json.dumps(dfm, indent=2, ensure_ascii=False).encode("utf-8"))
            add_artifact("reports/release-passport.json", json.dumps(release_passport, indent=2, ensure_ascii=False).encode("utf-8"))
            add_artifact("reports/kicad-drc.json", json.dumps(drc_report, indent=2, ensure_ascii=False).encode("utf-8"))

            bom_output = io.StringIO(newline="")
            writer = csv.writer(bom_output)
            writer.writerow(["Part", "Description", "Quantity", "Unit cost USD (estimate)", "Extended cost USD (estimate)", "Availability", "Alternatives"])
            for item in bom.get("items", []):
                writer.writerow([item.get("part"), item.get("description"), item.get("quantity"), item.get("unit_cost_usd"), round((item.get("quantity", 0) or 0) * (item.get("unit_cost_usd", 0) or 0), 2), item.get("availability"), "; ".join(item.get("alternatives", []))])
            add_artifact("reports/bom.csv", bom_output.getvalue().encode("utf-8"))

            if annotated_image:
                try:
                    add_artifact("reports/annotated-inspection.png", base64.b64decode(annotated_image, validate=True))
                except (ValueError, TypeError):
                    export_notes.append("Inspection annotation could not be decoded and was omitted.")

            for artifact in generated:
                add_artifact(f"fabrication/{artifact.relative_to(temp_path).as_posix()}", artifact.read_bytes())

            readme = "PCB Forge Fabrication Passport\n\n" + f"Release status: {release_status}\nBoard SHA-256: {board_hash}\n\n" + "\n".join(f"- {note}" for note in export_notes) + "\n\nSee reports/release-passport.json and reports/file-manifest.json for review evidence and file checksums. REVIEW REQUIRED means one or more checks were unavailable or incomplete. A release candidate is not a manufacturing guarantee; confirm files with the selected fabricator.\n"
            add_artifact("README.txt", readme.encode("utf-8"))
            add_artifact("reports/file-manifest.json", json.dumps({"board_sha256": board_hash, "manifest_covers": "all source, report and fabrication entries except this manifest", "files": file_manifest}, indent=2).encode("utf-8"))

    memory.seek(0)
    filename = f"{project_id.lower()}-manufacturing-passport.zip"
    return StreamingResponse(
        memory,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/{project_id}/workspace")
async def update_workspace(project_id: str, payload: dict):
    project = db.PROJECTS.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="PCB project not found.")
    if "physical_inspection" in payload:
        project["physical_inspection"] = payload["physical_inspection"]
    if "build_plan" in payload and payload["build_plan"] is not None:
        project["build_plan"] = payload["build_plan"]
    elif payload.get("build_plan") is None:
        project.pop("build_plan", None)
    db.save_project(project)
    if "physical_inspection" in payload and payload["physical_inspection"]:
        db.add_history(project_id, "inspection", "Gemma 4 hardware inspection saved")
    if payload.get("build_plan"):
        readiness = payload["build_plan"].get("build_plan", {}).get("manufacturing_readiness", "updated")
        db.add_history(project_id, "build_plan", f"Gemma 4 build plan saved: {readiness}")
    return {"id": project_id, "inspected": "physical_inspection" in project, "has_build_plan": "build_plan" in project}


@router.post("/{project_id}/analyze")
async def analyze_pcb(project_id: str):
    project = db.PROJECTS.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="PCB project not found.")

    revision_id = project.get("revision_id")
    if revision_id:
        db.set_revision_status(revision_id, "running")
    try:
        result = orchestrator.run_full_analysis(project_id, project["raw_path"])
    except Exception as e:
        if revision_id:
            db.set_revision_status(revision_id, "failed")
        logger.exception("PCB analysis failed for project %s", project_id)
        raise HTTPException(status_code=500, detail="PCB analysis failed. Check the backend log and verify the uploaded board file.") from e

    db.add_history(project_id, "analysis", "KiCad geometry, DFM, BOM, and supplier analysis completed")
    if revision_id:
        db.save_revision_analysis(revision_id, {
            "pcb_analysis": result["pcb_analysis"].model_dump(),
            "dfm_result": result["dfm_result"].model_dump(),
            "bom_result": result["bom_result"].model_dump(),
            "recommendation": result["recommendation"].model_dump(),
        }, tool_version=f"PCB Forge analysis pipeline; geometry source: {result['pcb_analysis'].source}")
    return {
        "pcb_analysis": result["pcb_analysis"],
        "dfm_result": result["dfm_result"],
        "bom_result": result["bom_result"],
        "recommendation": result["recommendation"],
    }


@router.post("/{project_id}/dfm")
async def get_dfm(project_id: str):
    project = db.PROJECTS.get(project_id)
    if not project or "dfm_result" not in project:
        raise HTTPException(status_code=404, detail="DFM result not available. Run /analyze first.")
    return project["dfm_result"]


@router.post("/{project_id}/bom")
async def get_bom(project_id: str):
    project = db.PROJECTS.get(project_id)
    if not project or "bom_result" not in project:
        raise HTTPException(status_code=404, detail="BOM result not available. Run /analyze first.")
    return project["bom_result"]


