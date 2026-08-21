# Contributing

Contributions should make the protocol safer, smaller, clearer, or more useful
without turning it into a domain-specific playbook.

## Before changing code or contracts

1. Open or update a scoped gap/proposal record when the change adds a new
   capability.
2. Inspect the tool inventory and repository history before adding a duplicate.
3. Preserve existing receipts. Amend a claim with a successor record rather
   than silently rewriting the evidence that supported it.
4. Keep the validator and example tools Python-standard-library only.

## Change requirements

- Preserve the four-state gap classification: `absent`, `present-unwired`,
  `broken`, and `unknown`.
- Keep no-overwrite behavior as the default for generated artifacts.
- Add focused tests for validator behavior and every tool behavior changed.
- Bound resource use and document side effects, inputs, outputs, exit codes,
  determinism, and limitations in the operator card.
- Record hashes/provenance for artifacts that support a claim.
- State nonclaims alongside important positive or negative evidence.
- Register every callable tool in `inventory/tools.json`.

## Local checks

```sh
python3 tools/ntnb.py validate --root .
python3 -m unittest discover -s tests -v
python3 -m json.tool .github/workflows/ci.yml >/dev/null
git status --short
git diff --check
```

Stage only the paths you intended to change. A passing test run is evidence for
the tested revision, not a universal guarantee.
