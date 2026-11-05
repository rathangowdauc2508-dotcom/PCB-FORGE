from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db
import knowledge


class KnowledgeRagTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_db = db.DB_PATH
        self.old_docs = knowledge.DOCUMENT_DIR
        db.DB_PATH = self.root / "test.sqlite3"
        knowledge.DOCUMENT_DIR = self.root / "docs"
        knowledge.DOCUMENT_DIR.mkdir()
        db.PROJECTS.clear()
        db.EVENTS.clear()
        db.init_db()
        knowledge.init_db()
        db.PROJECTS["PCB-A"] = {"id": "PCB-A", "filename": "a.kicad_pcb"}
        db.PROJECTS["PCB-B"] = {"id": "PCB-B", "filename": "b.kicad_pcb"}
        db.save_project(db.PROJECTS["PCB-A"])
        db.save_project(db.PROJECTS["PCB-B"])
        self.embed_patch = patch.object(knowledge, "_request_embeddings", return_value=None)
        self.embed_patch.start()

    def tearDown(self):
        self.embed_patch.stop()
        db.DB_PATH = self.old_db
        knowledge.DOCUMENT_DIR = self.old_docs
        db.PROJECTS.clear()
        db.EVENTS.clear()
        self.temp.cleanup()

    def upload(self, project, text, name="datasheet.txt", revision=None):
        source = self.root / ("upload-" + str(len(list(self.root.glob("upload-*")))) + Path(name).suffix)
        source.write_text(text, encoding="utf-8")
        return knowledge.ingest(source, name, project, revision)

    def test_ingestion_duplicate_detection_and_source_metadata(self):
        text = "# Power section\n\nU3 operates from a 3.3 V supply."
        first = self.upload("PCB-A", text)
        duplicate = self.upload("PCB-A", text)
        self.assertIn(first["status"], {"indexed", "indexed_lexical"})
        self.assertEqual(first["id"], duplicate["id"])
        self.assertTrue(duplicate["duplicate"])
        result = knowledge.retrieve("What voltage operates U3?", "PCB-A", None)
        self.assertTrue(result)
        self.assertEqual(result[0]["source_title"], "datasheet.txt")
        self.assertTrue(result[0]["id"].startswith("CHK-"))

    def test_document_versions_keep_only_latest_file_active(self):
        old = self.upload("PCB-A", "Old connector rating is 3 V.", name="connector.txt")
        current = self.upload("PCB-A", "Updated connector rating is 5 V.", name="connector.txt")
        self.assertEqual(current["document_version"], 2)
        self.assertEqual(current["is_active"], 1)
        self.assertEqual(knowledge.get_document(old["id"])["is_active"], 0)
        self.assertEqual(knowledge.retrieve("old 3V", "PCB-A", None), [])
        self.assertTrue(knowledge.retrieve("updated connector", "PCB-A", None))
    def test_project_documents_do_not_cross_project_boundaries(self):
        self.upload("PCB-A", "Connector J7 maximum voltage is 5 V.")
        self.assertTrue(knowledge.retrieve("J7 maximum voltage", "PCB-A", None))
        self.assertEqual(knowledge.retrieve("J7 maximum voltage", "PCB-B", None), [])

    def test_deleted_document_is_removed_from_retrieval(self):
        document = self.upload("PCB-A", "The thermal limit is 85 degrees Celsius.")
        self.assertTrue(knowledge.delete_document(document["id"]))
        self.assertEqual(knowledge.retrieve("thermal limit 85 degrees Celsius", "PCB-A", None), [])
        self.assertIsNone(knowledge.get_document(document["id"]))

    def test_missing_evidence_abstains_and_semantic_match_is_supported(self):
        self.assertTrue(knowledge.answer("Unknown component maximum voltage", [])["abstained"])
        self.upload(None, "This passage discusses switching regulator dissipation.")
        with patch.object(knowledge, "_request_embeddings", return_value=[[1.0, 0.0]]):
            vector = [1.0, 0.0]
            with knowledge._connection() as conn:
                conn.execute("UPDATE knowledge_chunks SET embedding_json=?, embedding_model=?", ('[1.0, 0.0]', knowledge.EMBEDDING_MODEL))
            result = knowledge.retrieve("heat conversion losses", None, None)
        self.assertTrue(result)
        self.assertEqual(result[0]["semantic_score"], 1.0)

    def test_list_documents_accepts_project_filter_and_pagination(self):
        shared = self.upload(None, "Shared resistor guidance.", name="shared.txt")
        project = self.upload("PCB-A", "Project capacitor guidance.", name="project.txt")

        project_docs = knowledge.list_documents("PCB-A", 50, 0)
        shared_docs = knowledge.list_documents(None, 50, 0)

        self.assertEqual({row["id"] for row in project_docs}, {shared["id"], project["id"]})
        self.assertEqual([row["id"] for row in shared_docs], [shared["id"]])

    def test_pdf_signature_is_validated(self):
        source = self.root / "bad.pdf"
        source.write_text("not a PDF", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "valid PDF signature"):
            knowledge.ingest(source, "bad.pdf", None, None)


if __name__ == "__main__":
    unittest.main()