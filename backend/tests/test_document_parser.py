from __future__ import annotations

import unittest
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


if __name__ == "__main__":
    unittest.main()
