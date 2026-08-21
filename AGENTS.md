# Agent Rules

These rules apply to the entire repository.

## Mission

When the parent goal needs a capability that is missing, do not stop at “there
is no tool.” Apply `TOOL-GAP-PROTOCOL.md`, produce bounded evidence, then return
to the parent goal. This repository is domain-agnostic; scope a project through
`no-tool-no-blocker.json` and records, not by weakening the shared doctrine.

## Zero-loss defaults

- Treat existing data, records, artifacts, and local changes as unique until
  provenance proves otherwise.
- Inventory and read before changing. Check Git status before and after work.
- Never overwrite an input, receipt, operator card, negative finding, or output
  by default. Create a new version or require an explicit operator flag.
- Never delete, reset, rewrite history, force-push, clean untracked files, or
  mutate an external system without explicit authorization and a verified exact
  target. Prefer recoverable operations.
- Do not stage unrelated files. Preserve concurrent work and do not revert it.
- Do not install a dependency merely to validate this repository. The validator,
  example, and tests must remain Python-standard-library only.
- Put temporary work under a verified temporary or project-scoped directory.
  Do not aim recursive operations at a workspace root, home directory, or an
  unresolved variable.

## Tool-gap contract

- Preserve the parent goal and its acceptance test before opening a tool lane.
- Classify a gap as exactly one of `absent`, `present-unwired`, `broken`, or
  `unknown`. Do not collapse “not found yet” into “absent.”
- Search the configured inventory and relevant project/system locations before
  building. Record commands, paths, timestamps, and findings.
- Reduce the need to the smallest binary question and choose the smallest
  sufficient response: wire, repair, acquire, build, or investigate.
- Bound runtime, bytes, concurrency, side effects, output locations, and any
  network access. Default to offline, read-only inputs and no overwrite.
- Use deterministic fixtures and assertions. Record hashes and provenance where
  inputs, implementations, or outputs affect the claim.
- A failed attempt is one observation. Negative claims require an exact scope,
  evidence hashes/provenance, explicit nonclaims, and an escape path.
- A new tool is unfinished until tests pass, an operator card contains complete
  usage, the tool is registered in the project inventory, and a return-to-goal
  receipt reconnects it to the parent goal.

## Validation

Run both commands before committing:

```sh
python3 tools/ntnb.py validate --root .
python3 -m unittest discover -s tests -v
```

If either command cannot run, report that as an exact scoped limitation; do not
claim validation passed.
