"""Foundry publishing pilot: exercise the actual portable persona producer."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_kit_portable as portable  # noqa: E402


class PortablePublicationTests(unittest.TestCase):
    def test_portable_output_matches_rendered_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "KIT_PORTABLE.md"
            size = portable.publish(target)
            self.assertEqual(target.read_text(encoding="utf-8"), portable.render())
            self.assertEqual(size, len(target.read_bytes()))

    def test_module_import_keeps_working(self):
        import importlib
        module = importlib.import_module("scripts.build_kit_portable")
        self.assertEqual(module.render(), portable.render())

    def test_failed_write_cannot_truncate_previous_portable_persona(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "KIT_PORTABLE.md"
            target.write_text("last good persona\n", encoding="utf-8")
            with patch.object(portable, "render", return_value="new persona\n"):
                with patch("_foundry_publish.os.replace", side_effect=OSError("injected rename failure")):
                    with self.assertRaises(OSError):
                        portable.publish(target)
            self.assertEqual(target.read_text(encoding="utf-8"), "last good persona\n")
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["KIT_PORTABLE.md"])


if __name__ == "__main__":
    unittest.main()
