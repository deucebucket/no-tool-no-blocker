from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.ntnb import DuplicateKeyError, Validator, load_json, sha256_file


ROOT = Path(__file__).resolve().parents[1]


class ValidatorTests(unittest.TestCase):
    def test_repository_is_valid(self) -> None:
        issues = Validator(ROOT).run()
        self.assertEqual([issue.render() for issue in issues], [])

    def test_hash_is_stable_and_lowercase(self) -> None:
        digest = sha256_file(ROOT / "examples/line-count/fixtures/three-lines.txt")
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual(digest, sha256_file(ROOT / "examples/line-count/fixtures/three-lines.txt"))

    def test_detects_artifact_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone = Path(directory) / "repo"
            shutil.copytree(ROOT, clone, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            fixture = clone / "examples/line-count/fixtures/three-lines.txt"
            fixture.write_bytes(fixture.read_bytes() + b"drift\n")
            messages = [issue.message for issue in Validator(clone).run()]
            self.assertTrue(any("mismatch" in message for message in messages), messages)

    def test_rejects_duplicate_json_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"id": "one", "id": "two"}\n', encoding="utf-8")
            with self.assertRaises(DuplicateKeyError):
                load_json(path)

    def test_workflow_is_json_formatted_yaml(self) -> None:
        workflow = load_json(ROOT / ".github/workflows/ci.yml")
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertIn("validate", workflow["jobs"])


if __name__ == "__main__":
    unittest.main()
