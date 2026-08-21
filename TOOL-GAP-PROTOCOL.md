# Tool-Gap Protocol

## Purpose

This protocol turns a missing or unusable capability into a bounded engineering
lane without losing the parent goal. Its governing sentence is:

> **No tool is not a blocker; it is a cue to scope and build the tool.**

“Build” includes wiring, repairing, configuring, or acquiring an existing tool
when that is the smallest truthful answer. The protocol is deliberately
project-agnostic. Project identity, paths, and default resource limits live in
`no-tool-no-blocker.json`; the doctrine does not need per-project edits.

## Core contracts

### Preserve the parent goal

Before opening a tool lane, record the parent goal ID, its acceptance test, the
single capability it lacks, and the artifact or decision the parent expects.
Tool work is a detour with an exit, not a replacement objective.

### Ask the smallest binary question

Write one question that can be answered **yes** or **no** by a bounded run. Good:
“Can this exact 2 MiB asset be decoded into a deterministic list of chunk
offsets?” Bad: “Can we understand the format?” If the question contains several
independent claims, split it.

The answer must identify its scope: inputs, versions or hashes, environment,
limits, and exclusions. “Yes for this fixture and revision” and “no under these
three attempted adapters” are useful answers. “It works” and “impossible” are
not.

### Classify current state exactly

Every gap assessment has exactly one state:

- `absent` — an inventory and bounded search found no candidate implementing
  the required capability in the declared scope.
- `present-unwired` — a plausible capability exists, but the parent workflow
  cannot currently call or reach it.
- `broken` — a known candidate was invoked correctly enough to test its contract
  and failed; the exact failure and revision are recorded.
- `unknown` — the evidence cannot yet distinguish the other states. Start here
  when search, wiring, invocation, or ownership is uncertain.

“Command not found” alone does not prove `absent`; the tool may be unregistered,
outside `PATH`, in another workspace, or available through a service. A single
failed invocation does not prove `broken` unless the expected invocation and
scope are established, and it never proves universal impossibility.

### Preserve evidence and data

Inputs are read-only by default. Outputs go to new explicit paths. Refuse to
overwrite unless an operator deliberately supplies a documented override.
Existing evidence records are append-only historical claims: supersede them
with a new record rather than editing away an old result.

Use SHA-256 for implementations, material inputs, outputs, and supporting
records when their bytes affect the claim. Record provenance: who or what
produced the artifact, the command, working directory, version or revision,
UTC time, and source location where relevant.

## Lifecycle

### 0. Anchor the parent goal

Create the gap assessment from `templates/gap-assessment.json` and fill:

- `parent_goal.id`, objective, acceptance test, and return artifact;
- one binary `question`;
- exact `scope` inputs, exclusions, environment, and bounds;
- initial state, often `unknown`.

Do not begin broad exploration until the question is small enough for one tool
or one evidence-producing probe.

### 1. Inventory and search before build

Read the configured `paths.tool_inventory`. Then run a bounded search across the
project, documented shared-tool locations, system command lookup, dependency
manifests, services, and prior evidence that are relevant to the capability.
Record exact commands and paths in `inventory_search`; redact secrets, but do
not replace facts with recollection.

For each candidate, decide whether it is:

- callable and already sufficient;
- implemented but unwired from the parent workflow;
- broken for the exact scoped case;
- adjacent but insufficient; or
- unverified.

Only classify `absent` after the declared search is complete. Record search
limits and an escape path for expanding it.

### 2. Choose the smallest response

Create a tool proposal and choose one decision:

- `reuse` — call a registered sufficient tool;
- `wire` — make an existing tool reachable;
- `repair` — restore a broken tool's declared contract;
- `acquire` — add an approved external tool when licensing, provenance, and
  placement allow it;
- `build` — implement the smallest missing capability;
- `investigate` — gather the evidence needed to leave `unknown`.

Compare candidates on question coverage, risk, dependencies, resource cost,
side effects, evidence quality, and time to return. Do not expand a one-shot
decoder into a framework or a small report into a platform.

The proposal must state success and stop conditions. A stop condition is not a
universal blocker; it routes to a named escape path or returns an exact negative
to the parent.

### 3. Set the safety envelope

Before execution, declare:

- maximum input bytes, runtime, memory if material, and concurrency;
- whether network access is required (default: no);
- read and write roots;
- side effects and cleanup behavior;
- no-overwrite behavior;
- accepted input formats and rejection behavior;
- handling of sensitive, licensed, or untrusted material.

If actual resource needs exceed the envelope, stop cleanly and revise the
proposal. Do not silently remove a bound to get a passing run.

### 4. Implement or connect the minimum

Keep inputs immutable. Separate discovery from mutation. Produce stable ordering
and serialization, explicit encodings, and documented exit codes. Avoid current
time, random data, absolute machine paths, network state, and locale-dependent
output unless the question requires them and they are recorded as inputs.

An error must be distinguishable from a negative answer. Never transform a
crash, timeout, partial output, skipped test, or missing dependency into `no`.

### 5. Test the contract

Focused tests must cover at least:

- the positive fixture that answers the binary question;
- a relevant negative or rejection case;
- no-overwrite behavior;
- the declared resource bound;
- deterministic repeated output when applicable.

Test with the same entry point documented for operators. Capture the tested
implementation hash and fixture/output hashes. If a test is not run, say so.

### 6. Write the operator card

The operator card is the callable contract, not a design summary. It must state:

- exact synopsis and copyable commands;
- runtime and dependency requirements;
- inputs, outputs, and formats;
- exit codes and error behavior;
- resource bounds, network use, and concurrency;
- side effects and overwrite policy;
- determinism and provenance behavior;
- limitations, nonclaims, and examples;
- implementation and test locations.

Someone unfamiliar with the implementation should be able to run the tool
safely from this card alone.

### 7. Register the tool

Add the tool to the configured inventory only after its callable contract and
tests exist. Registration includes a stable ID, status, implementation path and
SHA-256, operator card, tests, exact call shape, capabilities, and limitations.

Keep these operational states distinct:

- defined in source;
- callable in its documented environment;
- reachable from the parent workflow;
- owned or maintained.

An inventory entry proves registration, not continued health. If ongoing health
matters, give it an independent check.

### 8. Capture an evidence receipt

Run the exact operator command against pinned fixtures. The evidence receipt
records command, working directory, exit status, tool/revision provenance,
material artifact paths, sizes and SHA-256 hashes, assertions, observed answer,
and explicit nonclaims.

Evidence is deterministic when another operator can obtain the same material
output from the recorded inputs and implementation. Timestamps belong in the
receipt, not in deterministic tool output, unless time itself is an input.

### 9. Record truthful negative knowledge

Create a negative-knowledge record when a failed or insufficient path will save
future work. Its statement must be narrow enough to remain true. Include:

- exact claim and `as_of` UTC time;
- assessed inputs, versions, hashes, environment, and bounds;
- commands/search paths and observed results;
- evidence references with hashes;
- explicit nonclaims (what the evidence does **not** establish);
- at least one escape path with a trigger and next action.

Never generalize one timeout to “the service cannot do this,” one corrupt file
to “the format is unsupported,” or one failed build to “the project is blocked.”
Use: “revision X failed input hash Y under bound Z with error E; try A if B
changes.”

### 10. Return to the parent goal

The return-to-goal receipt closes the detour. It records the binary answer,
evidence receipt and hash, registered tool ID, remaining limitations, the exact
next parent command/action, and a return status.

Allowed return statuses are:

- `returned-with-capability` — the parent can now invoke the tool;
- `returned-with-evidence` — no new tool is needed, but the scoped answer is
  sufficient for the parent decision;
- `returned-with-scoped-negative` — the tested path failed or was insufficient,
  with an escape path that lets the parent choose the next route.

The tool lane is not complete merely because code exists or tests pass. It is
complete when the parent goal has received a usable capability or truthful
bounded answer and can resume.

## Record and validation rules

JSON records use UTF-8, schema version `1`, repository-relative POSIX paths, and
stable IDs. Use UTC timestamps ending in `Z`. Templates contain conspicuous
`replace-*` values; replace every one before placing a record in an active path.

Run:

```sh
python3 tools/ntnb.py validate --root .
python3 -m unittest discover -s tests -v
```

The validator checks required files, project configuration, active record
shapes, state vocabularies, binary questions, cross-references, implementation
and evidence hashes, inventory registration, no-overwrite defaults, positive
resource bounds, return linkage, and CI workflow structure. It cannot prove the
truth of prose claims, authorize side effects, or replace independent review.

## Decision summary

```text
parent goal -> smallest binary question -> classify
                                      |
                         inventory + bounded search
                                      |
                reuse | wire | repair | acquire | build | investigate
                                      |
                   bounded implementation / invocation
                                      |
              tests -> operator card -> inventory -> evidence
                                      |
              exact negative if useful -> return receipt
                                      |
                              resume parent goal
```
