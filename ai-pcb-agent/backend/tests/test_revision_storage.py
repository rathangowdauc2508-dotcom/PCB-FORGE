from __future__ import annotations

import asyncio
import io

import pytest
from fastapi import HTTPException

import db
import routes.pcb as pcb_routes
from models import Manufacturer, ManufacturingQuote, PCBAnalysis
from tools.manufacturer_service import recommend
from tools.dfm_checker import run_dfm_checks
from tools.pcb_parser import analyze_pcb_file


BOARD = b'''(kicad_pcb (version 20241229) (layers (0 "F.Cu" signal) (31 "B.Cu" signal))
(gr_rect (start 0 0) (end 20 10) (layer "Edge.Cuts") (width 0.05))
(segment (start 1 1) (end 2 2) (width 0.2) (layer "F.Cu"))
(via (at 3 3) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu")))'''


@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")
    db.PROJECTS.clear()
    db.EVENTS.clear()
    db.init_db()
    project = {"id": "PCB-TEST", "filename": "board.kicad_pcb"}
    db.PROJECTS[project["id"]] = project
    db.save_project(project)
    return tmp_path


def test_revision_records_keep_order_parent_and_exact_analysis(isolated_database):
    first = db.create_board_revision("PCB-TEST", "board.kicad_pcb", "first.kicad_pcb", "a" * 64, 12, "2026-01-01T00:00:00Z")
    second = db.create_board_revision("PCB-TEST", "board.kicad_pcb", "second.kicad_pcb", "b" * 64, 13, "2026-01-02T00:00:00Z", first["id"])
    db.PROJECTS["PCB-TEST"]["revision_id"] = second["id"]
    db.save_project(db.PROJECTS["PCB-TEST"])
    result = {"source": "test-parser", "dfm": {"status": "WARNING"}}
    db.save_revision_analysis(second["id"], result, "test-tool 1")

    revisions = db.list_board_revisions("PCB-TEST")
    assert [row["revision_number"] for row in revisions] == [2, 1]
    assert revisions[0]["parent_revision_id"] == first["id"]
    assert db.get_board_revision(second["id"])["analysis"] == result
    assert revisions[0]["sha256"] == "b" * 64


def test_parent_revision_must_belong_to_same_project(isolated_database):
    with pytest.raises(ValueError, match="does not belong"):
        db.create_board_revision("PCB-TEST", "board.kicad_pcb", "board", "c" * 64, 1, "now", "REV-OTHER")


def test_parser_reports_unknown_measurements_instead_of_demo_values(tmp_path):
    source = tmp_path / "board.kicad_pcb"
    source.write_bytes(BOARD)
    parsed = analyze_pcb_file(str(source))
    assert parsed["board_width_mm"] == 20
    assert parsed["board_height_mm"] == 10
    assert parsed["min_trace_width_mm"] == 0.2
    assert parsed["min_clearance_mm"] is None
    assert parsed["board_edge_clearance_mm"] is None


def test_parser_counts_power_copper_layers_not_kicad_layer_ids(tmp_path):
    source = tmp_path / "four_layer_board.kicad_pcb"
    source.write_text('''(kicad_pcb (version 20250101)
(layers (0 "F.Cu" signal) (1 "In1.Cu" power) (2 "In2.Cu" power)
(31 "B.Cu" signal) (36 "B.SilkS" user) (44 "Edge.Cuts" user)))
(footprint "test" (at 1 1)))''')
    parsed = analyze_pcb_file(str(source))
    assert parsed["layers"] == 4


def test_unverified_dfm_is_not_described_as_incompatible():
    quote = ManufacturingQuote(
        manufacturer_id="test", manufacturer_name="Test Fabricator", price_usd=12,
        lead_time_days=7, dfm_compatible=None, layer_compatible=True, score=70,
        reasons=["one or more DFM checks could not be evaluated"],
    )
    result = recommend([quote])
    assert "unverified" in result.explanation.lower()
    assert "does not satisfy" not in result.explanation.lower()

def test_dfm_does_not_pass_checks_with_missing_measurements():
    board = PCBAnalysis(
        board_width_mm=None, board_height_mm=None, area_mm2=None, layers=2,
        components=0, footprints=0, pads=0, vias=0, tracks=0, zones=0,
        min_trace_width_mm=None, min_clearance_mm=None, min_drill_diameter_mm=None,
        board_edge_clearance_mm=None, source="test",
    )
    manufacturer = Manufacturer(
        id="test", name="Test", base_price_usd=1, lead_time_days=1, max_layers=4,
        min_trace_width_mm=0.1, min_clearance_mm=0.1, min_drill_diameter_mm=0.2, rating=4,
    )
    result = run_dfm_checks(board, manufacturer)
    assert result.status == "WARNING"
    assert any(check.passed is None for check in result.checks)
    assert result.passed_checks < result.total_checks
