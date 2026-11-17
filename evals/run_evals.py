#!/usr/bin/env python3
"""Golden evals. Deterministic: no timestamps, sorted output.
Writes evals/eval_report.json (byte-identical across runs)."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import governance as gov

HERE = os.path.dirname(os.path.abspath(__file__))
cases = []
def case(cid, ok, detail):
    cases.append({"id": cid, "passed": bool(ok), "detail": detail})

# Illegal transitions (8 planted)
ILLEGAL = [("draft", "published"), ("draft", "retired"), ("retired", "draft"),
           ("retired", "published"), ("published", "draft"), ("published", "in_review"),
           ("deprecated", "published"), ("in_review", "deprecated")]
for frm, to in ILLEGAL:
    reg = gov.seed_registry()
    s = gov.find_skill(reg, "calendar-helper"); s["lifecycle_state"] = frm
    log = []
    ok, reason = gov.transition(reg, "calendar-helper", to, log=log)
    case(f"illegal_{frm}_to_{to}", (not ok) and log and not log[-1]["ok"], reason)

# Gate failures: 5 in_review plants, each with exactly its named rule
EXPECTED_GATE = {"ownerless-plugin": ["owner_missing"],
                 "contract-broken": ["contract_check_failed"],
                 "eval-missing": ["eval_evidence_missing"],
                 "eval-low": ["eval_score_below_threshold"],
                 "version-stalled": ["version_not_increased"]}
reg = gov.seed_registry()
for sid, exp in sorted(EXPECTED_GATE.items()):
    g = gov.evaluate_gate(gov.find_skill(reg, sid))
    case(f"gate_{sid}", (not g["passed"]) and g["failures"] == exp, ",".join(g["failures"]))
# A clean published skill passes the gate
g = gov.evaluate_gate(gov.find_skill(reg, "core-retrieval"))
case("gate_clean_skill_passes", g["passed"] and g["failures"] == [], "pass")

# Blast radius: hub pinned set, leaf empty, deprecated excluded
hub = gov.blast_radius(reg, gov.HUB_SKILL)
case("blast_hub_skills_exact", hub["affected_skills"] == gov.HUB_BLAST_SKILLS, ",".join(hub["affected_skills"]))
case("blast_hub_agents_exact", hub["affected_agents"] == gov.HUB_BLAST_AGENTS, ",".join(hub["affected_agents"]))
case("blast_hub_excludes_deprecated", "legacy-parser" not in hub["affected_skills"], "legacy-parser deprecated")
leaf = gov.blast_radius(reg, "executive-brief")
case("blast_leaf_empty", leaf["affected_skills"] == [] and leaf["affected_agents"] == [], "empty")

# Intake verdicts: planted adopt/wait/pass set
EXPECTED_INTAKE = {"prop-adopt-a": "adopt", "prop-adopt-b": "adopt",
                   "prop-wait-a": "wait", "prop-wait-b": "wait",
                   "prop-pass-a": "pass", "prop-pass-b": "pass"}
for p in gov.seed_proposals():
    r = gov.evaluate_intake(p, reg)
    case(f"intake_{p['id']}", r["verdict"] == EXPECTED_INTAKE[p["id"]],
         f"{r['verdict']} score={r['score']} timebox={r['timebox_weeks']}")

# Registry invariants + determinism
case("check_seeded_registry_clean", gov.check_registry(reg) == [], "0 findings")
case("determinism_gate_repeat", gov.evaluate_gate(gov.find_skill(reg, "eval-low")) ==
     gov.evaluate_gate(gov.find_skill(gov.seed_registry(), "eval-low")), "stable")

report = {"total": len(cases), "passed": sum(1 for c in cases if c["passed"]),
          "failed": sum(1 for c in cases if not c["passed"]), "cases": cases}
out = os.path.join(HERE, "eval_report.json")
with open(out, "w") as f:
    json.dump(report, f, indent=2, sort_keys=True); f.write("\n")
print(json.dumps({"total": report["total"], "passed": report["passed"], "failed": report["failed"]}, sort_keys=True))
sys.exit(0 if report["failed"] == 0 else 1)
