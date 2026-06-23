from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import app.document_parser as document_parser


class DocumentParserTests(unittest.TestCase):
    def test_doc_extraction_falls_back_to_libreoffice_when_antiword_is_broken(self) -> None:
        def fake_which(name: str) -> str | None:
            if name == "antiword":
                return "/usr/bin/antiword"
            return None

        with (
            patch.object(document_parser.shutil, "which", side_effect=fake_which),
            patch.object(document_parser.subprocess, "run", side_effect=OSError("Exec format error")),
            patch.object(document_parser, "_extract_via_libreoffice", return_value="Текст технического задания") as libreoffice,
        ):
            text = document_parser._extract_doc(Path("broken.doc"))

        self.assertEqual(text, "Текст технического задания")
        libreoffice.assert_called_once()

    def test_zip_archive_extracts_member_documents_as_one_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "parts.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("part-1.txt", "Первая часть ТЗ: насос ЦНС 60-330")
                archive.writestr("nested/part-2.txt", "Вторая часть ТЗ: количество 3 шт.")

            text, status = document_parser.extract_text(archive_path)

        self.assertEqual(status, "archive_ok")
        self.assertIn("=== ARCHIVE FILE:", text)
        self.assertIn("Первая часть ТЗ", text)
        self.assertIn("Вторая часть ТЗ", text)

    def test_docx_extension_archive_falls_back_to_archive_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "documentation.docx"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("Техническое задание.txt", "Огнезащитный материал, количество 2106 кг")

            text, status = document_parser.extract_text(archive_path)

        self.assertEqual(status, "docx_archive_archive_ok")
        self.assertIn("Огнезащитный материал", text)


if __name__ == "__main__":
    unittest.main()
