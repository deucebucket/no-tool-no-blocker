from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "examples/line-count/tool/line_count.py"
FIXTURE = ROOT / "examples/line-count/fixtures/three-lines.txt"
EXPECTED = ROOT / "examples/line-count/expected/report.json"


class ExampleToolTests(unittest.TestCase):
    def run_tool(self, input_path: Path, output_path: Path, max_bytes: int = 1024) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--max-bytes",
                str(max_bytes),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

    def test_pinned_fixture_matches_expected_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            result = self.run_tool(FIXTURE, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_bytes(), EXPECTED.read_bytes())
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["byte_count"], 18)
            self.assertEqual(report["lf_line_count"], 3)

    def test_output_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            self.assertEqual(self.run_tool(FIXTURE, first).returncode, 0)
            self.assertEqual(self.run_tool(FIXTURE, second).returncode, 0)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.json"
            original = b"preserve me\n"
            output.write_bytes(original)
            result = self.run_tool(FIXTURE, output)
            self.assertEqual(result.returncode, 4)
            self.assertIn("refusing to overwrite", result.stderr)
            self.assertEqual(output.read_bytes(), original)

    def test_rejects_input_over_bound_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            result = self.run_tool(FIXTURE, output, max_bytes=17)
            self.assertEqual(result.returncode, 3)
            self.assertIn("limit is 17 bytes", result.stderr)
            self.assertFalse(output.exists())

    def test_rejects_invalid_utf8_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "invalid.bin"
            output = Path(directory) / "report.json"
            input_path.write_bytes(b"valid\n\xff\n")
            result = self.run_tool(input_path, output)
            self.assertEqual(result.returncode, 3)
            self.assertIn("not valid UTF-8", result.stderr)
            self.assertFalse(output.exists())

    def test_rejects_nonpositive_bound_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            result = self.run_tool(FIXTURE, output, max_bytes=0)
            self.assertEqual(result.returncode, 3)
            self.assertIn("positive integer", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
