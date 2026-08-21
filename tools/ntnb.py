#!/usr/bin/env python3
"""Deterministically validate No Tool, No Blocker records using stdlib only."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
BINARY_QUESTION_RE = re.compile(
    r"^(can|does|do|is|are|will|did|has|have|was|were|should)\b", re.IGNORECASE
)
GAP_STATES = {"absent", "present-unwired", "broken", "unknown"}
DECISIONS = {"reuse", "wire", "repair", "acquire", "build", "investigate"}
EVIDENCE_STATUSES = {"pass", "fail", "error"}
RETURN_STATUSES = {
    "returned-with-capability",
    "returned-with-evidence",
    "returned-with-scoped-negative",
}
REQUIRED_FILES = (
    "README.md",
    "AGENTS.md",
    "TOOL-GAP-PROTOCOL.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "LICENSE",
    "no-tool-no-blocker.json",
    "inventory/tools.json",
    ".github/workflows/ci.yml",
)
TEMPLATE_TYPES = {
    "project-scope.json": "project-scope",
    "gap-assessment.json": "gap-assessment",
    "tool-proposal.json": "tool-proposal",
    "operator-card.json": "operator-card",
    "evidence-receipt.json": "evidence-receipt",
    "negative-knowledge.json": "negative-knowledge",
    "return-to-goal-receipt.json": "return-to-goal-receipt",
}
PATH_KEYS = {
    "gap_records": "gap-assessment",
    "tool_proposals": "tool-proposal",
    "operator_cards": "operator-card",
    "evidence_receipts": "evidence-receipt",
    "negative_knowledge": "negative-knowledge",
    "return_receipts": "return-to-goal-receipt",
}


class DuplicateKeyError(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=_unique_object)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class Issue:
    path: str
    message: str

    def render(self) -> str:
        return f"{self.path}: {self.message}"


class Validator:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.issues: list[Issue] = []
        self.counts: dict[str, int] = {}
        self.project_id = ""
        self.inventory: dict[str, dict[str, Any]] = {}
        self.records: dict[str, dict[str, dict[str, Any]]] = {}
        self.record_paths: dict[str, Path] = {}

    def issue(self, path: Path | str, message: str) -> None:
        if isinstance(path, Path):
            try:
                label = path.resolve().relative_to(self.root).as_posix()
            except ValueError:
                label = str(path)
        else:
            label = path
        self.issues.append(Issue(label, message))

    def require(self, condition: bool, path: Path | str, message: str) -> bool:
        if not condition:
            self.issue(path, message)
            return False
        return True

    def run(self) -> list[Issue]:
        self._check_required_files()
        config_path = self.root / "no-tool-no-blocker.json"
        if not config_path.is_file():
            return self.issues
        try:
            config = load_json(config_path)
        except (OSError, UnicodeError, json.JSONDecodeError, DuplicateKeyError) as exc:
            self.issue(config_path, f"cannot parse JSON: {exc}")
            return self.issues
        if not isinstance(config, dict):
            self.issue(config_path, "top level must be an object")
            return self.issues
        self._check_config(config_path, config)
        self._check_templates()
        self._load_inventory(config)
        self._load_records(config)
        self._check_cross_references(config)
        self._check_workflow()
        return sorted(self.issues, key=lambda item: (item.path, item.message))

    def _check_required_files(self) -> None:
        for relative in REQUIRED_FILES:
            if not (self.root / relative).is_file():
                self.issue(relative, "required file is missing")

    def _check_config(self, path: Path, data: dict[str, Any]) -> None:
        self.require(data.get("schema_version") == 1, path, "schema_version must be 1")
        self.require(data.get("record_type") == "project-scope", path, "record_type must be project-scope")
        project = self._object(data, "project", path)
        project_id = project.get("id")
        if self._id(project_id, path, "project.id"):
            self.project_id = project_id
        self._nonempty_string(project.get("name"), path, "project.name")
        self._nonempty_string(project.get("primary_goal"), path, "project.primary_goal")
        self.require(project.get("root") == ".", path, "project.root must be '.' in a template checkout")
        self._nonempty_list(project.get("domains"), path, "project.domains")

        paths = self._object(data, "paths", path)
        self._relative_path(paths.get("tool_inventory"), path, "paths.tool_inventory")
        for key in PATH_KEYS:
            patterns = self._nonempty_list(paths.get(key), path, f"paths.{key}")
            for pattern in patterns:
                if isinstance(pattern, str):
                    self._relative_path(pattern, path, f"paths.{key} item", allow_glob=True)

        defaults = self._object(data, "defaults", path)
        self.require(defaults.get("hash_algorithm") == "sha256", path, "defaults.hash_algorithm must be sha256")
        self.require(defaults.get("overwrite") is False, path, "defaults.overwrite must be false")
        self.require(defaults.get("network") is False, path, "defaults.network must be false")
        for key in ("max_runtime_seconds", "max_input_bytes", "max_concurrency"):
            self._positive_int(defaults.get(key), path, f"defaults.{key}")

    def _check_templates(self) -> None:
        for filename, expected_type in TEMPLATE_TYPES.items():
            path = self.root / "templates" / filename
            if not path.is_file():
                self.issue(path, "required template is missing")
                continue
            try:
                data = load_json(path)
            except (OSError, UnicodeError, json.JSONDecodeError, DuplicateKeyError) as exc:
                self.issue(path, f"cannot parse JSON: {exc}")
                continue
            if not isinstance(data, dict):
                self.issue(path, "top level must be an object")
                continue
            self.require(data.get("schema_version") == 1, path, "schema_version must be 1")
            self.require(data.get("record_type") == expected_type, path, f"record_type must be {expected_type}")

    def _load_inventory(self, config: dict[str, Any]) -> None:
        raw = config.get("paths", {}).get("tool_inventory")
        if not isinstance(raw, str):
            return
        path = self.root / raw
        try:
            data = load_json(path)
        except (OSError, UnicodeError, json.JSONDecodeError, DuplicateKeyError) as exc:
            self.issue(path, f"cannot parse inventory JSON: {exc}")
            return
        if not isinstance(data, dict):
            self.issue(path, "inventory top level must be an object")
            return
        self.require(data.get("schema_version") == 1, path, "schema_version must be 1")
        self.require(data.get("record_type") == "tool-inventory", path, "record_type must be tool-inventory")
        self.require(data.get("project_id") == self.project_id, path, "project_id must match project scope")
        tools = data.get("tools")
        if not isinstance(tools, list):
            self.issue(path, "tools must be a list")
            return
        for index, tool in enumerate(tools):
            label = f"tools[{index}]"
            if not isinstance(tool, dict):
                self.issue(path, f"{label} must be an object")
                continue
            tool_id = tool.get("id")
            if not self._id(tool_id, path, f"{label}.id"):
                continue
            if tool_id in self.inventory:
                self.issue(path, f"duplicate tool id: {tool_id}")
                continue
            self.inventory[tool_id] = tool
            self._nonempty_string(tool.get("name"), path, f"{label}.name")
            self.require(tool.get("status") in {"proposed", "active", "retired", "broken"}, path, f"{label}.status is invalid")
            implementation = tool.get("implementation")
            if self._relative_path(implementation, path, f"{label}.implementation"):
                self._file_hash(implementation, tool.get("implementation_sha256"), path, f"{label}.implementation_sha256")
            self._relative_path(tool.get("operator_card"), path, f"{label}.operator_card")
            tests = self._nonempty_list(tool.get("tests"), path, f"{label}.tests")
            for test_path in tests:
                if self._relative_path(test_path, path, f"{label}.tests item"):
                    self.require((self.root / test_path).is_file(), path, f"registered test does not exist: {test_path}")
            self._nonempty_string(tool.get("call"), path, f"{label}.call")
            self._nonempty_list(tool.get("capabilities"), path, f"{label}.capabilities")
            self._nonempty_list(tool.get("limitations"), path, f"{label}.limitations")
        self.counts["tools"] = len(self.inventory)

    def _load_records(self, config: dict[str, Any]) -> None:
        paths = config.get("paths", {})
        for key, expected_type in PATH_KEYS.items():
            type_records: dict[str, dict[str, Any]] = {}
            for pattern in paths.get(key, []):
                if not isinstance(pattern, str):
                    continue
                for path in sorted(self.root.glob(pattern)):
                    if not path.is_file():
                        continue
                    try:
                        data = load_json(path)
                    except (OSError, UnicodeError, json.JSONDecodeError, DuplicateKeyError) as exc:
                        self.issue(path, f"cannot parse JSON: {exc}")
                        continue
                    if not isinstance(data, dict):
                        self.issue(path, "top level must be an object")
                        continue
                    self.require(data.get("schema_version") == 1, path, "schema_version must be 1")
                    self.require(data.get("record_type") == expected_type, path, f"record_type must be {expected_type}")
                    record_id = data.get("tool_id") if expected_type == "operator-card" else data.get("id")
                    if not self._id(record_id, path, "record id"):
                        continue
                    if record_id in type_records:
                        self.issue(path, f"duplicate {expected_type} id: {record_id}")
                        continue
                    type_records[record_id] = data
                    self.record_paths[f"{expected_type}:{record_id}"] = path
                    self._check_record(expected_type, path, data)
            self.records[expected_type] = type_records
            self.counts[expected_type] = len(type_records)

    def _check_record(self, kind: str, path: Path, data: dict[str, Any]) -> None:
        if kind == "gap-assessment":
            self._check_gap(path, data)
        elif kind == "tool-proposal":
            self._check_proposal(path, data)
        elif kind == "operator-card":
            self._check_operator(path, data)
        elif kind == "evidence-receipt":
            self._check_evidence(path, data)
        elif kind == "negative-knowledge":
            self._check_negative(path, data)
        elif kind == "return-to-goal-receipt":
            self._check_return(path, data)

    def _common_project(self, path: Path, data: dict[str, Any]) -> None:
        self.require(data.get("project_id") == self.project_id, path, "project_id must match project scope")

    def _check_gap(self, path: Path, data: dict[str, Any]) -> None:
        self._common_project(path, data)
        self._timestamp(data.get("created_at"), path, "created_at")
        parent = self._object(data, "parent_goal", path)
        self._id(parent.get("id"), path, "parent_goal.id")
        for key in ("objective", "acceptance_test", "return_artifact"):
            self._nonempty_string(parent.get(key), path, f"parent_goal.{key}")
        self._binary_question(data.get("question"), path, "question")
        self._id(data.get("required_capability"), path, "required_capability")
        self.require(data.get("state") in GAP_STATES, path, f"state must be one of {sorted(GAP_STATES)}")
        scope = self._object(data, "scope", path)
        self._nonempty_list(scope.get("inputs"), path, "scope.inputs")
        self._nonempty_list(scope.get("exclusions"), path, "scope.exclusions")
        self._nonempty_string(scope.get("environment"), path, "scope.environment")
        self._bounds(scope, path, "scope")
        search = self._object(data, "inventory_search", path)
        self._relative_path(search.get("inventory_path"), path, "inventory_search.inventory_path")
        self._timestamp(search.get("performed_at"), path, "inventory_search.performed_at")
        self._nonempty_list(search.get("commands"), path, "inventory_search.commands")
        self._nonempty_list(search.get("paths"), path, "inventory_search.paths")
        self._nonempty_string(search.get("conclusion"), path, "inventory_search.conclusion")
        self._nonempty_list(search.get("limitations"), path, "inventory_search.limitations")
        self._nonempty_list(data.get("nonclaims"), path, "nonclaims")
        self._escape_paths(data.get("escape_paths"), path)
        self.require(data.get("status") in {"open", "closed", "superseded"}, path, "status is invalid")

    def _check_proposal(self, path: Path, data: dict[str, Any]) -> None:
        self._common_project(path, data)
        self._timestamp(data.get("created_at"), path, "created_at")
        self._id(data.get("gap_id"), path, "gap_id")
        self._id(data.get("parent_goal_id"), path, "parent_goal_id")
        self.require(data.get("decision") in DECISIONS, path, f"decision must be one of {sorted(DECISIONS)}")
        self._nonempty_string(data.get("selected_approach"), path, "selected_approach")
        self._nonempty_string(data.get("success_condition"), path, "success_condition")
        self._nonempty_list(data.get("stop_conditions"), path, "stop_conditions")
        safety = self._object(data, "safety", path)
        self._nonempty_list(safety.get("read_roots"), path, "safety.read_roots")
        self._nonempty_list(safety.get("write_roots"), path, "safety.write_roots")
        self._bounds(safety, path, "safety")
        self.require(safety.get("overwrite") is False, path, "safety.overwrite must be false")
        deliverables = self._object(data, "deliverables", path)
        for key in ("implementation", "operator_card", "evidence_receipt", "inventory"):
            self._relative_path(deliverables.get(key), path, f"deliverables.{key}")
        tests = self._nonempty_list(deliverables.get("tests"), path, "deliverables.tests")
        for value in tests:
            self._relative_path(value, path, "deliverables.tests item")
        self._nonempty_list(data.get("risks"), path, "risks")
        self._nonempty_list(data.get("nonclaims"), path, "nonclaims")

    def _check_operator(self, path: Path, data: dict[str, Any]) -> None:
        tool_id = data.get("tool_id")
        self._id(tool_id, path, "tool_id")
        self._nonempty_string(data.get("name"), path, "name")
        self._nonempty_string(data.get("version"), path, "version")
        self.require(data.get("status") in {"proposed", "active", "retired", "broken"}, path, "status is invalid")
        implementation = self._object(data, "implementation", path)
        impl_path = implementation.get("path")
        if self._relative_path(impl_path, path, "implementation.path"):
            self._file_hash(impl_path, implementation.get("sha256"), path, "implementation.sha256")
        self._nonempty_string(data.get("purpose"), path, "purpose")
        self._binary_question(data.get("answers_question"), path, "answers_question")
        runtime = self._object(data, "runtime", path)
        self._nonempty_string(runtime.get("command"), path, "runtime.command")
        self._nonempty_list(runtime.get("requirements"), path, "runtime.requirements")
        self._nonempty_list(runtime.get("dependencies"), path, "runtime.dependencies")
        self.require(isinstance(runtime.get("network"), bool), path, "runtime.network must be boolean")
        usage = self._object(data, "usage", path)
        self._nonempty_string(usage.get("synopsis"), path, "usage.synopsis")
        self._nonempty_string(usage.get("working_directory"), path, "usage.working_directory")
        self._nonempty_list(usage.get("examples"), path, "usage.examples")
        self._nonempty_list(data.get("inputs"), path, "inputs")
        outputs = self._nonempty_list(data.get("outputs"), path, "outputs")
        for output in outputs:
            if isinstance(output, dict):
                self.require(output.get("creation") == "new-file-only", path, "every output.creation must be new-file-only")
        exit_codes = self._object(data, "exit_codes", path)
        self.require("0" in exit_codes, path, "exit_codes must document 0")
        self._bounds(self._object(data, "resource_bounds", path), path, "resource_bounds", network_optional=True)
        self._nonempty_list(data.get("side_effects"), path, "side_effects")
        self.require(data.get("overwrite_policy") == "refuse", path, "overwrite_policy must be refuse")
        for key in ("determinism", "provenance"):
            self._nonempty_string(data.get(key), path, key)
        self._nonempty_list(data.get("tests"), path, "tests")
        self._nonempty_list(data.get("limitations"), path, "limitations")
        self._nonempty_list(data.get("nonclaims"), path, "nonclaims")

    def _check_evidence(self, path: Path, data: dict[str, Any]) -> None:
        self._common_project(path, data)
        self._timestamp(data.get("created_at"), path, "created_at")
        for key in ("parent_goal_id", "gap_id", "tool_id"):
            self._id(data.get(key), path, key)
        self._binary_question(data.get("question"), path, "question")
        self.require(isinstance(data.get("observed_answer"), bool), path, "observed_answer must be boolean")
        status = data.get("status")
        self.require(status in EVIDENCE_STATUSES, path, f"status must be one of {sorted(EVIDENCE_STATUSES)}")
        execution = self._object(data, "execution", path)
        self._nonempty_string(execution.get("command"), path, "execution.command")
        self._relative_path(execution.get("cwd"), path, "execution.cwd")
        self._timestamp(execution.get("started_at"), path, "execution.started_at")
        self._nonempty_string(execution.get("environment"), path, "execution.environment")
        self.require(isinstance(execution.get("exit_code"), int), path, "execution.exit_code must be an integer")
        if status == "pass":
            self.require(execution.get("exit_code") == 0, path, "passing evidence must have exit_code 0")
        artifacts = self._nonempty_list(data.get("artifacts"), path, "artifacts")
        roles: set[str] = set()
        for index, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict):
                self.issue(path, f"artifacts[{index}] must be an object")
                continue
            role = artifact.get("role")
            if isinstance(role, str):
                roles.add(role)
            artifact_path = artifact.get("path")
            if self._relative_path(artifact_path, path, f"artifacts[{index}].path"):
                self._file_hash(artifact_path, artifact.get("sha256"), path, f"artifacts[{index}].sha256", artifact.get("bytes"))
        self.require({"implementation", "input", "output"}.issubset(roles), path, "artifacts must include implementation, input, and output roles")
        self._nonempty_list(data.get("assertions"), path, "assertions")
        provenance = self._object(data, "provenance", path)
        for key in ("operator", "tool_version", "source_revision"):
            self._nonempty_string(provenance.get(key), path, f"provenance.{key}")
        self._sha256(provenance.get("implementation_sha256"), path, "provenance.implementation_sha256")
        self._nonempty_list(data.get("nonclaims"), path, "nonclaims")
        self._nonempty_list(data.get("reproduction"), path, "reproduction")

    def _check_negative(self, path: Path, data: dict[str, Any]) -> None:
        self._common_project(path, data)
        self._timestamp(data.get("as_of"), path, "as_of")
        self._id(data.get("gap_id"), path, "gap_id")
        self._nonempty_string(data.get("claim"), path, "claim")
        scope = self._object(data, "scope", path)
        for key in ("inputs", "versions", "bounds"):
            self._nonempty_list(scope.get(key), path, f"scope.{key}")
        self._nonempty_string(scope.get("environment"), path, "scope.environment")
        basis = self._nonempty_list(data.get("basis"), path, "basis")
        for index, item in enumerate(basis):
            if not isinstance(item, dict):
                self.issue(path, f"basis[{index}] must be an object")
                continue
            basis_path = item.get("path")
            if self._relative_path(basis_path, path, f"basis[{index}].path"):
                self._file_hash(basis_path, item.get("sha256"), path, f"basis[{index}].sha256")
            self._nonempty_string(item.get("summary"), path, f"basis[{index}].summary")
        provenance = self._object(data, "search_provenance", path)
        self._nonempty_list(provenance.get("commands"), path, "search_provenance.commands")
        self._nonempty_list(provenance.get("paths"), path, "search_provenance.paths")
        self._nonempty_string(provenance.get("result"), path, "search_provenance.result")
        nonclaims = self._nonempty_list(data.get("nonclaims"), path, "nonclaims")
        self.require(len(nonclaims) >= 2, path, "negative knowledge must include at least two explicit nonclaims")
        self._escape_paths(data.get("escape_paths"), path)
        self.require(data.get("status") in {"active", "superseded"}, path, "status is invalid")

    def _check_return(self, path: Path, data: dict[str, Any]) -> None:
        self._common_project(path, data)
        self._timestamp(data.get("created_at"), path, "created_at")
        for key in ("parent_goal_id", "gap_id", "tool_id"):
            self._id(data.get(key), path, key)
        self.require(data.get("resolution_status") in RETURN_STATUSES, path, f"resolution_status must be one of {sorted(RETURN_STATUSES)}")
        self.require(isinstance(data.get("binary_answer"), bool), path, "binary_answer must be boolean")
        evidence = self._object(data, "evidence", path)
        evidence_path = evidence.get("path")
        if self._relative_path(evidence_path, path, "evidence.path"):
            self._file_hash(evidence_path, evidence.get("sha256"), path, "evidence.sha256")
        registration = self._object(data, "inventory_registration", path)
        self._relative_path(registration.get("path"), path, "inventory_registration.path")
        self._id(registration.get("tool_id"), path, "inventory_registration.tool_id")
        self._nonempty_list(data.get("remaining_limits"), path, "remaining_limits")
        self._nonempty_string(data.get("next_parent_action"), path, "next_parent_action")
        self._nonempty_list(data.get("artifacts"), path, "artifacts")
        self._nonempty_list(data.get("nonclaims"), path, "nonclaims")
        self._nonempty_string(data.get("closed_by"), path, "closed_by")

    def _check_cross_references(self, config: dict[str, Any]) -> None:
        gaps = self.records.get("gap-assessment", {})
        proposals = self.records.get("tool-proposal", {})
        operators = self.records.get("operator-card", {})
        evidence = self.records.get("evidence-receipt", {})
        negatives = self.records.get("negative-knowledge", {})
        returns = self.records.get("return-to-goal-receipt", {})

        for record_id, proposal in proposals.items():
            path = self.record_paths[f"tool-proposal:{record_id}"]
            self.require(proposal.get("gap_id") in gaps, path, f"unknown gap_id: {proposal.get('gap_id')}")
        for tool_id, card in operators.items():
            path = self.record_paths[f"operator-card:{tool_id}"]
            self.require(tool_id in self.inventory, path, f"operator tool is not registered: {tool_id}")
            inventory_card = self.inventory.get(tool_id, {}).get("operator_card")
            expected = path.relative_to(self.root).as_posix()
            self.require(inventory_card == expected, path, f"inventory operator_card must be {expected}")
            inventory_hash = self.inventory.get(tool_id, {}).get("implementation_sha256")
            card_hash = card.get("implementation", {}).get("sha256")
            self.require(inventory_hash == card_hash, path, "inventory and operator implementation hashes differ")
        for record_id, receipt in evidence.items():
            path = self.record_paths[f"evidence-receipt:{record_id}"]
            self.require(receipt.get("gap_id") in gaps, path, f"unknown gap_id: {receipt.get('gap_id')}")
            self.require(receipt.get("tool_id") in self.inventory, path, f"unregistered tool_id: {receipt.get('tool_id')}")
            gap = gaps.get(receipt.get("gap_id"), {})
            self.require(receipt.get("parent_goal_id") == gap.get("parent_goal", {}).get("id"), path, "parent_goal_id differs from gap")
            self.require(receipt.get("question") == gap.get("question"), path, "question differs from gap")
            tool_hash = self.inventory.get(receipt.get("tool_id"), {}).get("implementation_sha256")
            self.require(receipt.get("provenance", {}).get("implementation_sha256") == tool_hash, path, "evidence implementation hash differs from inventory")
        for record_id, negative in negatives.items():
            path = self.record_paths[f"negative-knowledge:{record_id}"]
            self.require(negative.get("gap_id") in gaps, path, f"unknown gap_id: {negative.get('gap_id')}")
        for record_id, returned in returns.items():
            path = self.record_paths[f"return-to-goal-receipt:{record_id}"]
            gap_id = returned.get("gap_id")
            tool_id = returned.get("tool_id")
            self.require(gap_id in gaps, path, f"unknown gap_id: {gap_id}")
            self.require(tool_id in self.inventory, path, f"unregistered tool_id: {tool_id}")
            gap = gaps.get(gap_id, {})
            self.require(returned.get("parent_goal_id") == gap.get("parent_goal", {}).get("id"), path, "parent_goal_id differs from gap")
            evidence_path = returned.get("evidence", {}).get("path")
            linked = [
                receipt for receipt_id, receipt in evidence.items()
                if self.record_paths[f"evidence-receipt:{receipt_id}"].relative_to(self.root).as_posix() == evidence_path
            ]
            self.require(len(linked) == 1, path, "evidence.path must identify exactly one configured evidence receipt")
            if linked:
                self.require(linked[0].get("gap_id") == gap_id, path, "linked evidence belongs to a different gap")
                self.require(linked[0].get("tool_id") == tool_id, path, "linked evidence belongs to a different tool")
                self.require(linked[0].get("observed_answer") == returned.get("binary_answer"), path, "binary_answer differs from linked evidence")
            registration = returned.get("inventory_registration", {})
            self.require(registration.get("path") == config.get("paths", {}).get("tool_inventory"), path, "inventory registration path differs from project scope")
            self.require(registration.get("tool_id") == tool_id, path, "inventory registration tool_id differs from return tool_id")

    def _check_workflow(self) -> None:
        path = self.root / ".github/workflows/ci.yml"
        if not path.is_file():
            return
        try:
            data = load_json(path)
        except (OSError, UnicodeError, json.JSONDecodeError, DuplicateKeyError) as exc:
            self.issue(path, f"workflow must be JSON-formatted YAML and parse as JSON: {exc}")
            return
        if not isinstance(data, dict):
            self.issue(path, "workflow top level must be an object")
            return
        self._nonempty_string(data.get("name"), path, "name")
        self.require("on" in data, path, "workflow must define on")
        self.require(data.get("permissions") == {"contents": "read"}, path, "workflow permissions must be contents: read only")
        jobs = self._object(data, "jobs", path)
        self.require(bool(jobs), path, "workflow must define at least one job")
        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                self.issue(path, f"jobs.{job_id} must be an object")
                continue
            self._nonempty_string(job.get("runs-on"), path, f"jobs.{job_id}.runs-on")
            steps = self._nonempty_list(job.get("steps"), path, f"jobs.{job_id}.steps")
            for index, step in enumerate(steps):
                if not isinstance(step, dict):
                    self.issue(path, f"jobs.{job_id}.steps[{index}] must be an object")
                    continue
                self._nonempty_string(step.get("name"), path, f"jobs.{job_id}.steps[{index}].name")
                self.require(bool(step.get("uses") or step.get("run")), path, f"jobs.{job_id}.steps[{index}] needs uses or run")

    def _object(self, data: dict[str, Any], key: str, path: Path) -> dict[str, Any]:
        value = data.get(key)
        if not isinstance(value, dict):
            self.issue(path, f"{key} must be an object")
            return {}
        return value

    def _nonempty_string(self, value: Any, path: Path | str, field: str) -> bool:
        return self.require(isinstance(value, str) and bool(value.strip()), path, f"{field} must be a non-empty string")

    def _nonempty_list(self, value: Any, path: Path | str, field: str) -> list[Any]:
        if not isinstance(value, list) or not value:
            self.issue(path, f"{field} must be a non-empty list")
            return []
        return value

    def _positive_int(self, value: Any, path: Path | str, field: str) -> bool:
        return self.require(isinstance(value, int) and not isinstance(value, bool) and value > 0, path, f"{field} must be a positive integer")

    def _bounds(self, data: dict[str, Any], path: Path, prefix: str, network_optional: bool = False) -> None:
        for key in ("max_runtime_seconds", "max_input_bytes", "max_concurrency"):
            self._positive_int(data.get(key), path, f"{prefix}.{key}")
        if not network_optional:
            self.require(isinstance(data.get("network"), bool), path, f"{prefix}.network must be boolean")

    def _id(self, value: Any, path: Path | str, field: str) -> bool:
        return self.require(isinstance(value, str) and bool(ID_RE.fullmatch(value)), path, f"{field} must match {ID_RE.pattern}")

    def _sha256(self, value: Any, path: Path | str, field: str) -> bool:
        return self.require(isinstance(value, str) and bool(SHA256_RE.fullmatch(value)), path, f"{field} must be 64 lowercase hex characters")

    def _timestamp(self, value: Any, path: Path, field: str) -> bool:
        if not self.require(isinstance(value, str) and value.endswith("Z"), path, f"{field} must be a UTC timestamp ending in Z"):
            return False
        try:
            datetime.fromisoformat(value[:-1] + "+00:00")
        except ValueError:
            self.issue(path, f"{field} is not a valid RFC 3339 timestamp")
            return False
        return True

    def _binary_question(self, value: Any, path: Path, field: str) -> bool:
        if not self._nonempty_string(value, path, field):
            return False
        return self.require(value.endswith("?") and bool(BINARY_QUESTION_RE.match(value)), path, f"{field} must be phrased as one answerable yes-or-no question")

    def _relative_path(self, value: Any, path: Path | str, field: str, allow_glob: bool = False) -> bool:
        if not self._nonempty_string(value, path, field):
            return False
        if "\\" in value:
            self.issue(path, f"{field} must use POSIX separators")
            return False
        parsed = PurePosixPath(value)
        if parsed.is_absolute() or ".." in parsed.parts:
            self.issue(path, f"{field} must be repository-relative without '..'")
            return False
        if not allow_glob and any(char in value for char in "*?["):
            self.issue(path, f"{field} must not contain a glob")
            return False
        return True

    def _file_hash(self, relative: Any, expected: Any, record_path: Path, field: str, expected_bytes: Any = None) -> None:
        if not isinstance(relative, str) or not self._sha256(expected, record_path, field):
            return
        target = self.root / relative
        if not target.is_file():
            self.issue(record_path, f"hashed file does not exist: {relative}")
            return
        actual = sha256_file(target)
        self.require(actual == expected, record_path, f"{field} mismatch for {relative}: expected {expected}, got {actual}")
        if expected_bytes is not None:
            self.require(isinstance(expected_bytes, int) and expected_bytes >= 0, record_path, f"byte count for {relative} must be a non-negative integer")
            if isinstance(expected_bytes, int):
                actual_bytes = target.stat().st_size
                self.require(actual_bytes == expected_bytes, record_path, f"byte count mismatch for {relative}: expected {expected_bytes}, got {actual_bytes}")

    def _escape_paths(self, value: Any, path: Path) -> None:
        items = self._nonempty_list(value, path, "escape_paths")
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                self.issue(path, f"escape_paths[{index}] must be an object")
                continue
            self._nonempty_string(item.get("trigger"), path, f"escape_paths[{index}].trigger")
            self._nonempty_string(item.get("action"), path, f"escape_paths[{index}].action")


def command_validate(args: argparse.Namespace) -> int:
    validator = Validator(args.root)
    issues = validator.run()
    if issues:
        for issue in issues:
            print(f"ERROR {issue.render()}", file=sys.stderr)
        print(f"validation failed: {len(issues)} issue(s)", file=sys.stderr)
        return 1
    summary = ", ".join(f"{key}={value}" for key, value in sorted(validator.counts.items()))
    print(f"validation passed: {summary}")
    return 0


def command_hash(args: argparse.Namespace) -> int:
    path = args.path
    if not path.is_file():
        print(f"error: not a regular file: {path}", file=sys.stderr)
        return 2
    print(json.dumps({"bytes": path.stat().st_size, "path": path.as_posix(), "sha256": sha256_file(path)}, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ntnb", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate project records and hashes")
    validate.add_argument("--root", type=Path, default=Path("."), help="repository root (default: current directory)")
    validate.set_defaults(handler=command_validate)
    hash_command = subparsers.add_parser("hash", help="print deterministic SHA-256 and byte count")
    hash_command.add_argument("path", type=Path)
    hash_command.set_defaults(handler=command_hash)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
