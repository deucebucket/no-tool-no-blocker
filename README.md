# No Tool, No Blocker

> **No tool is not a blocker; it is a cue to scope and build the tool.**

This is a project-agnostic template for turning a missing capability into the
smallest trustworthy tool, proving what it does, registering it, and returning
to the work that needed it. It applies to software, research, art pipelines,
data work, operations, and other evidence-driven projects.

The protocol does not assume that every gap requires new code. A capability may
be absent, present but unwired, broken, or still unknown. Inventory and search
come first; wiring or repairing an existing tool is often the smallest answer.

## Start a project

Use this repository as a GitHub template, then clone the new repository. Edit
only `no-tool-no-blocker.json` to establish the project's identity, goals,
artifact locations, and resource bounds. The core doctrine remains reusable.

```sh
git clone git@github.com:YOUR-OWNER/YOUR-PROJECT.git
cd YOUR-PROJECT
$EDITOR no-tool-no-blocker.json
python3 tools/ntnb.py validate --root .
python3 -m unittest discover -s tests -v
```

For an existing project, copy this repository's files into a dedicated
directory, set `project.root` in `no-tool-no-blocker.json`, and register that
directory in the parent project's documentation.

## Work a tool gap

1. Read [TOOL-GAP-PROTOCOL.md](TOOL-GAP-PROTOCOL.md).
2. Copy the seven JSON templates without overwriting an existing record.
3. Reduce the need to the smallest binary question.
4. Classify the gap and search the declared inventory before proposing work.
5. Wire, repair, acquire, or build the smallest sufficient tool.
6. Test it, write its operator card, register it, and record deterministic
   evidence.
7. Write a return receipt and resume the parent goal.

Example setup commands:

```sh
mkdir -p gaps proposals operator-cards evidence knowledge/negative returns
cp -n templates/gap-assessment.json gaps/gap-YYYYMMDD-short-name.json
cp -n templates/tool-proposal.json proposals/tool-YYYYMMDD-short-name.json
cp -n templates/operator-card.json operator-cards/tool-short-name.json
cp -n templates/evidence-receipt.json evidence/evidence-YYYYMMDD-short-name.json
cp -n templates/negative-knowledge.json knowledge/negative/negative-YYYYMMDD-short-name.json
cp -n templates/return-to-goal-receipt.json returns/return-YYYYMMDD-short-name.json
python3 tools/ntnb.py validate --root .
```

`cp -n` is intentional: records are no-overwrite by default. If a claim changes,
create a successor record and preserve the old one as history.

## Commands

```sh
# Validate contracts, cross-references, hashes, inventory, and CI structure.
python3 tools/ntnb.py validate --root .

# Produce the SHA-256 and size used by evidence records.
python3 tools/ntnb.py hash path/to/artifact

# Run the focused test suite.
python3 -m unittest discover -s tests -v

# Validate that the JSON-formatted GitHub Actions workflow is valid JSON/YAML.
python3 -m json.tool .github/workflows/ci.yml >/dev/null

# Run the complete filled example. The output path must not already exist.
tmp_dir="$(mktemp -d)"
python3 examples/line-count/tool/line_count.py \
  --input examples/line-count/fixtures/three-lines.txt \
  --output "$tmp_dir/report.json" \
  --max-bytes 1024
diff -u examples/line-count/expected/report.json "$tmp_dir/report.json"
```

The validator and example tool use only the Python standard library. Nothing
needs to be installed.

## Repository map

- `no-tool-no-blocker.json` — the only initial project-scoping configuration.
- `TOOL-GAP-PROTOCOL.md` — lifecycle, evidence, safety, and truthfulness contract.
- `templates/` — copy-first records for every protocol stage.
- `inventory/tools.json` — callable tool registry, including the filled example.
- `examples/line-count/` — a complete gap-to-return worked example.
- `tools/ntnb.py` — deterministic validator and hashing CLI.
- `tests/` — focused unit and integration tests.

## What a tool does not prove

A passing tool proves only its recorded question, inputs, implementation hash,
environment, and observed outputs. It does not prove every input, platform,
workflow, or future version. Negative findings are equally scoped: one failed
attempt is evidence about that attempt, never a universal blocker.

## License

Released under [CC0 1.0 Universal](LICENSE).
