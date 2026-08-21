#!/usr/bin/env python3
"""Count LF bytes in a bounded UTF-8 file and emit deterministic JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


class ContractError(Exception):
    """An input or resource bound violated the operator contract."""


def build_report(input_path: Path, max_bytes: int) -> dict[str, int | str]:
    if max_bytes <= 0:
        raise ContractError("--max-bytes must be a positive integer")
    try:
        if not input_path.is_file():
            raise ContractError(f"input is not a regular file: {input_path}")
        stated_size = input_path.stat().st_size
        if stated_size > max_bytes:
            raise ContractError(
                f"input is {stated_size} bytes; limit is {max_bytes} bytes"
            )
        with input_path.open("rb") as stream:
            data = stream.read(max_bytes + 1)
    except OSError as exc:
        raise ContractError(f"cannot read input: {exc}") from exc

    if len(data) > max_bytes:
        raise ContractError(f"input grew beyond the {max_bytes}-byte limit")
    try:
        data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ContractError(f"input is not valid UTF-8: {exc}") from exc

    return {
        "byte_count": len(data),
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "lf_line_count": data.count(b"\n"),
    }


def encode_report(report: dict[str, int | str]) -> bytes:
    return (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_new(output_path: Path, payload: bytes) -> None:
    try:
        with output_path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError as exc:
        raise FileExistsError(f"output exists; refusing to overwrite: {output_path}") from exc


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Count LF bytes in a bounded UTF-8 file and write deterministic JSON."
    )
    result.add_argument("--input", required=True, type=Path, help="read-only UTF-8 input")
    result.add_argument("--output", required=True, type=Path, help="new JSON output path")
    result.add_argument("--max-bytes", required=True, type=int, help="positive input bound")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = build_report(args.input, args.max_bytes)
        payload = encode_report(report)
        write_new(args.output, payload)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"error: cannot create output: {exc}", file=sys.stderr)
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
