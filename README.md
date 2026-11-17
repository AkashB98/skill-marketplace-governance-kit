# skill-marketplace-governance-kit

Governance for a fictional internal marketplace of agent skills: a lifecycle
state machine, a publishing gate, a deprecation blast-radius check, and a
fixed intake rubric — so a skill is only published with evidence, only
deprecated with its impact known, and only adopted through a scored gate.

**What it proves about Akash:** he can design the operating system around AI
skills, not just the skills themselves — lifecycle policy, evidence-based
publishing, dependency-aware deprecation, and intake triage, all enforced in
code with golden evals. JD-backed: Harvey's Senior AI Enablement Engineer
(GTM) role asks for exactly this — governance and publishing/deprecation
standards for an internal skill/plugin marketplace, with an eval intake gate.

## Headline results (seeded fixtures, all re-runnable)

- **15 seeded skills** — 9 published, 1 deprecated, 5 in review
- **5 / 5 planted gate failures caught**, each with its own named rule:
  `owner_missing`, `contract_check_failed`, `eval_evidence_missing`,
  `eval_score_below_threshold`, `version_not_increased`
- **8 / 8 planted illegal transitions rejected and logged** (e.g.
  `draft → published`, `retired → anything`, `published → draft`)
- **Hub blast radius pinned:** deprecating `core-retrieval` affects exactly
  **7 published skills** (briefing-builder, doc-summarizer, email-drafter,
  executive-brief, knowledge-search, support-responder, ticket-triage) and
  **6 agents** (Briefing, Executive, Helpdesk, Outreach, Research, Support)
- **Intake verdicts: 2 adopt / 2 wait / 2 pass** across 6 planted proposals
- **51 tests passing · 26/26 golden evals passing**, eval report byte-identical
  across 3 runs

## How it works

- **Registry** — each skill carries `id`, `name`, `owner`, `version`,
  `lifecycle_state`, `contract_check`, `eval_evidence` (present? score,
  threshold), `depends_on`, and `consumed_by`.
- **Lifecycle** — `draft → in_review → published → deprecated → retired`,
  plus `in_review → draft` (changes requested). Everything else is rejected
  and logged with a reason.
- **Publishing gate** (`in_review → published`) — requires
  `contract_check == "pass"`, eval evidence present with score ≥ threshold,
  a named non-empty owner, and a version strictly greater than the skill's
  previously published version ("must go up" only — no semver range solving).
  Each rule fails independently with a named reason.
- **Blast radius** — walks the reverse dependency graph from a skill and
  returns the exact set of *published* skills that transitively depend on it,
  plus the agents consuming those skills.
- **Intake gate** — one fixed rubric (not a workflow engine): 5 criteria ×
  1 point — success criteria defined, eval plan present, owner named, not a
  duplicate of an existing skill, timebox ≤ 4 weeks. Score 5 = **adopt**,
  3–4 = **wait**, 0–2 = **pass**. The timebox is recorded on every record.

## Run it

```bash
python3 cli.py generate    # seed data/registry.json + data/proposals.json
python3 cli.py registry    # dump the registry
python3 cli.py transition ownerless-plugin published   # rejected: gate_failed:owner_missing
python3 cli.py gate eval-low
python3 cli.py impact core-retrieval
python3 cli.py intake      # all proposals; or: intake prop-adopt-a
python3 cli.py report
python3 cli.py check       # exit 0 = published skills satisfy gate invariants,
                           # 1 = findings, 2 = bad input (missing/corrupt registry)
python3 cli.py demo        # end-to-end walkthrough, exit 0
python3 cli.py serve --port 8765   # stdlib http.server on 127.0.0.1:
                                   # GET /health, POST /gate {"skill_id": "..."}
python3 run_tests.py       # 51 tests
python3 evals/run_evals.py # 26 golden evals -> evals/eval_report.json
```

Python standard library only. No installs, no network, no keys.

## Sibling boundaries

- `contract_check` is an **input field only**. This kit never re-validates a
  skill's internals — that is **agent-skill-contract-kit**'s job.
- There is deliberately **no access policy and no joiner/mover/leaver logic**
  here — that is **mcp-gateway-governance-kit**'s job.

## POC framing

This is a proof of concept over synthetic fixtures, built to make the
governance rules executable and testable: the gate, state machine, blast
radius, and rubric are real code with pinned expected outcomes, while the
marketplace itself (15 skills, 6 proposals) is fictional sample data a real
deployment would load from its own registry.

## Honest limits

- Fixtures only — no real marketplace, registry service, or skill runtime.
- `contract_check` is trusted as an input, not re-validated (see above).
- No access control, authentication, or access policy of any kind.
- Version comparison is simple dotted-numeric "must go up", not full semver.
- The intake rubric is one fixed scoring sheet by design, not a configurable
  workflow engine.

## Dev-loop note

The first blast-radius draft walked the reverse graph and reported 8 affected
skills for `core-retrieval` — it had swept in `legacy-parser`, which depends
on the hub but is already deprecated. The pinned golden eval caught it: blast
radius is about live impact, so only *published* dependents count. The tests
now pin that exclusion explicitly (`test_deprecated_excluded`), and the hub
set is locked at exactly 7 skills / 6 agents.

## License

MIT — Akash Bhargava.
