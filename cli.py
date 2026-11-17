#!/usr/bin/env python3
"""CLI: generate / registry / transition / gate / impact / intake /
report / check / demo / serve. Stdlib only.

check exit codes: 0 = all published skills satisfy gate invariants,
1 = findings present, 2 = bad input (missing/corrupt registry file).
"""
import argparse, json, os, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
import governance as gov

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
REG_PATH = os.path.join(DATA, "registry.json")
PROP_PATH = os.path.join(DATA, "proposals.json")
LOG_PATH = os.path.join(DATA, "transition_log.jsonl")

def _dump(obj):
    print(json.dumps(obj, indent=2, sort_keys=True))

def _load(path, seed):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return seed()

def load_registry():
    return _load(REG_PATH, gov.seed_registry)

def load_proposals():
    return _load(PROP_PATH, gov.seed_proposals)

def cmd_generate(_):
    os.makedirs(DATA, exist_ok=True)
    with open(REG_PATH, "w") as f: json.dump(gov.seed_registry(), f, indent=2, sort_keys=True)
    with open(PROP_PATH, "w") as f: json.dump(gov.seed_proposals(), f, indent=2, sort_keys=True)
    _dump({"generated": [REG_PATH, PROP_PATH], "skills": len(gov.SKILLS), "proposals": len(gov.PROPOSALS)})
    return 0

def cmd_registry(_):
    _dump(load_registry()); return 0

def cmd_transition(a):
    reg, log = load_registry(), []
    ok, reason = gov.transition(reg, a.skill_id, a.to_state, log=log)
    os.makedirs(DATA, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        for e in log: f.write(json.dumps(e, sort_keys=True) + "\n")
    if ok:
        with open(REG_PATH, "w") as f: json.dump(reg, f, indent=2, sort_keys=True)
    _dump({"ok": ok, "reason": reason, "log": log})
    return 0 if ok else 1

def cmd_gate(a):
    s = gov.find_skill(load_registry(), a.skill_id)
    if s is None: _dump({"error": "skill_not_found"}); return 2
    g = gov.evaluate_gate(s); _dump(g); return 0 if g["passed"] else 1

def cmd_impact(a):
    reg = load_registry()
    if gov.find_skill(reg, a.skill_id) is None: _dump({"error": "skill_not_found"}); return 2
    _dump(gov.blast_radius(reg, a.skill_id)); return 0

def cmd_intake(a):
    reg, props = load_registry(), load_proposals()
    if a.proposal_id:
        p = next((x for x in props if x["id"] == a.proposal_id), None)
        if p is None: _dump({"error": "proposal_not_found"}); return 2
        _dump(gov.evaluate_intake(p, reg))
    else:
        _dump([gov.evaluate_intake(p, reg) for p in props])
    return 0

def cmd_report(_):
    reg, props = load_registry(), load_proposals()
    by_state = {}
    for s in reg: by_state[s["lifecycle_state"]] = by_state.get(s["lifecycle_state"], 0) + 1
    verdicts = {}
    for p in props:
        v = gov.evaluate_intake(p, reg)["verdict"]; verdicts[v] = verdicts.get(v, 0) + 1
    gate_failures = {s["id"]: gov.evaluate_gate(s)["failures"] for s in reg
                     if s["lifecycle_state"] == "in_review" and not gov.evaluate_gate(s)["passed"]}
    _dump({"skills_total": len(reg), "by_state": by_state,
           "hub_blast_radius": gov.blast_radius(reg, gov.HUB_SKILL),
           "in_review_gate_failures": gate_failures, "intake_verdicts": verdicts,
           "check_findings": gov.check_registry(reg)})
    return 0

def cmd_check(_):
    if os.path.exists(REG_PATH):
        try:
            with open(REG_PATH) as f: reg = json.load(f)
            if not isinstance(reg, list): raise ValueError("registry must be a list")
        except Exception as e:
            print(json.dumps({"error": f"bad_input: {e}"})); return 2
    else:
        reg = gov.seed_registry()
    findings = gov.check_registry(reg)
    _dump({"findings": findings, "ok": not findings})
    return 0 if not findings else 1

def cmd_demo(_):
    reg, log = gov.seed_registry(), []
    steps = []
    ok, reason = gov.transition(reg, "calendar-helper", "published", log=log)
    steps.append({"step": "illegal published->published attempt on calendar-helper", "ok": ok, "reason": reason})
    ok, reason = gov.transition(reg, "ownerless-plugin", "published", log=log)
    steps.append({"step": "gate-blocked publish of ownerless-plugin", "ok": ok, "reason": reason})
    steps.append({"step": "hub blast radius", "result": gov.blast_radius(reg, gov.HUB_SKILL)})
    steps.append({"step": "intake verdicts",
                  "result": {p["id"]: gov.evaluate_intake(p, reg)["verdict"] for p in gov.seed_proposals()}})
    steps.append({"step": "check", "findings": gov.check_registry(reg)})
    _dump({"demo": steps})
    print("demo: OK")
    return 0

def cmd_serve(a):
    reg = load_registry()
    class H(BaseHTTPRequestHandler):
        def log_message(self, *x): pass
        def _send(self, code, obj):
            body = json.dumps(obj, sort_keys=True).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            self._send(200, {"status": "ok"}) if self.path == "/health" else self._send(404, {"error": "not_found"})
        def do_POST(self):
            if self.path != "/gate": self._send(404, {"error": "not_found"}); return
            try:
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            except Exception:
                self._send(400, {"error": "bad_json"}); return
            skill = payload.get("skill") or gov.find_skill(reg, payload.get("skill_id", ""))
            if skill is None: self._send(404, {"error": "skill_not_found"}); return
            self._send(200, gov.evaluate_gate(skill))
    HTTPServer(("127.0.0.1", a.port), H).serve_forever()
    return 0

def main(argv=None):
    p = argparse.ArgumentParser(prog="skill-marketplace-governance")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("generate"); sub.add_parser("registry"); sub.add_parser("report")
    sub.add_parser("check"); sub.add_parser("demo")
    t = sub.add_parser("transition"); t.add_argument("skill_id"); t.add_argument("to_state")
    g = sub.add_parser("gate"); g.add_argument("skill_id")
    i = sub.add_parser("impact"); i.add_argument("skill_id")
    k = sub.add_parser("intake"); k.add_argument("proposal_id", nargs="?")
    s = sub.add_parser("serve"); s.add_argument("--port", type=int, default=8765)
    a = p.parse_args(argv)
    fn = {"generate": cmd_generate, "registry": cmd_registry, "transition": cmd_transition,
          "gate": cmd_gate, "impact": cmd_impact, "intake": cmd_intake, "report": cmd_report,
          "check": cmd_check, "demo": cmd_demo, "serve": cmd_serve}[a.cmd]
    return fn(a)

if __name__ == "__main__":
    sys.exit(main())
