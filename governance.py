"""Core governance logic for a fictional internal skill marketplace.

Stdlib only. contract_check is an INPUT field only -- this kit never
re-validates skill internals (that is agent-skill-contract-kit's job).
No access policy lives here (that is mcp-gateway-governance-kit's job).
"""
import copy

ALLOWED_TRANSITIONS = {
    "draft": {"in_review"},
    "in_review": {"published", "draft"},
    "published": {"deprecated"},
    "deprecated": {"retired"},
    "retired": set(),
}
STATES = tuple(ALLOWED_TRANSITIONS.keys())
TIMEBOX_CAP_WEEKS = 4

def _v(version):
    try:
        return tuple(int(p) for p in str(version).split("."))
    except Exception:
        return (0,)

def _skill(sid, name, owner, version, prev, state, contract, score, thr, deps, agents):
    ev = ({"present": True, "score": score, "threshold": thr} if score is not None
          else {"present": False, "score": None, "threshold": thr})
    return {"id": sid, "name": name, "owner": owner, "version": version,
            "previous_published_version": prev, "lifecycle_state": state,
            "contract_check": contract, "eval_evidence": ev,
            "depends_on": list(deps), "consumed_by": list(agents)}

# 15 seeded skills: 9 published, 1 deprecated, 5 in_review (one isolated
# gate failure each: owner / contract / eval-missing / eval-low / version).
SKILLS = [
    _skill("core-retrieval", "Core Retrieval", "Priya Nair", "2.1.0", "2.0.0", "published", "pass", 0.92, 0.85, [], ["Research Agent"]),
    _skill("doc-summarizer", "Doc Summarizer", "Marco Silva", "1.4.0", "1.3.0", "published", "pass", 0.89, 0.80, ["core-retrieval"], ["Briefing Agent"]),
    _skill("ticket-triage", "Ticket Triage", "Lena Ortiz", "1.2.0", "1.1.0", "published", "pass", 0.88, 0.80, ["core-retrieval"], ["Support Agent"]),
    _skill("knowledge-search", "Knowledge Search", "Ken Watanabe", "3.0.0", "2.9.0", "published", "pass", 0.91, 0.85, ["core-retrieval"], ["Research Agent", "Helpdesk Agent"]),
    _skill("email-drafter", "Email Drafter", "Sofia Rossi", "1.1.0", "1.0.0", "published", "pass", 0.86, 0.80, ["doc-summarizer"], ["Outreach Agent"]),
    _skill("briefing-builder", "Briefing Builder", "David Okafor", "2.0.0", "1.9.0", "published", "pass", 0.90, 0.85, ["doc-summarizer", "knowledge-search"], ["Briefing Agent"]),
    _skill("support-responder", "Support Responder", "Ana Costa", "1.3.0", "1.2.0", "published", "pass", 0.87, 0.80, ["ticket-triage"], ["Support Agent"]),
    _skill("executive-brief", "Executive Brief", "Raj Patel", "1.0.0", "0.9.0", "published", "pass", 0.93, 0.85, ["briefing-builder"], ["Executive Agent"]),
    _skill("calendar-helper", "Calendar Helper", "Maya Chen", "1.5.0", "1.4.0", "published", "pass", 0.90, 0.80, [], ["Scheduling Agent"]),
    _skill("legacy-parser", "Legacy Parser", "Tom Becker", "0.8.0", "0.7.0", "deprecated", "pass", 0.84, 0.80, ["core-retrieval"], ["Legacy Agent"]),
    _skill("ownerless-plugin", "Ownerless Plugin", "", "1.0.0", None, "in_review", "pass", 0.90, 0.80, [], []),
    _skill("contract-broken", "Contract Broken", "Ivy Zhang", "1.0.0", None, "in_review", "fail", 0.90, 0.80, [], []),
    _skill("eval-missing", "Eval Missing", "Omar Farouk", "1.0.0", None, "in_review", "pass", None, 0.80, [], []),
    _skill("eval-low", "Eval Low", "Nina Petrova", "1.0.0", None, "in_review", "pass", 0.60, 0.85, [], []),
    _skill("version-stalled", "Version Stalled", "Chris Doyle", "1.0.0", "1.0.0", "in_review", "pass", 0.90, 0.80, [], []),
]

# Pinned hub blast radius (published transitive dependents of core-retrieval).
HUB_SKILL = "core-retrieval"
HUB_BLAST_SKILLS = ["briefing-builder", "doc-summarizer", "email-drafter",
                    "executive-brief", "knowledge-search", "support-responder",
                    "ticket-triage"]
HUB_BLAST_AGENTS = ["Briefing Agent", "Executive Agent", "Helpdesk Agent",
                    "Outreach Agent", "Research Agent", "Support Agent"]

def _prop(pid, name, owner, success, eval_plan, duplicate_of, weeks):
    return {"id": pid, "name": name, "owner": owner,
            "success_criteria_defined": success, "eval_plan_present": eval_plan,
            "duplicate_of": duplicate_of, "timebox_weeks": weeks}

PROPOSALS = [
    _prop("prop-adopt-a", "Slide Outline Builder", "Hana Kim", True, True, None, 3),
    _prop("prop-adopt-b", "Changelog Writer", "Leo Martins", True, True, None, 2),
    _prop("prop-wait-a", "FAQ Answer Drafter", "Erin Walsh", True, False, None, 3),
    _prop("prop-wait-b", "Survey Summarizer", "Paul Novak", False, False, None, 4),
    _prop("prop-pass-a", "Doc Summarizer Clone", "", True, False, "doc-summarizer", 8),
    _prop("prop-pass-b", "Unscoped Helper", "", False, False, None, 9),
]

TRANSITION_LOG = []

def seed_registry():
    return copy.deepcopy(SKILLS)

def seed_proposals():
    return copy.deepcopy(PROPOSALS)

def find_skill(registry, skill_id):
    for s in registry:
        if s["id"] == skill_id:
            return s
    return None

def can_transition(frm, to):
    return to in ALLOWED_TRANSITIONS.get(frm, set())

def transition(registry, skill_id, to_state, log=None):
    """Returns (ok, reason). Illegal transitions are rejected AND logged."""
    log = TRANSITION_LOG if log is None else log
    skill = find_skill(registry, skill_id)
    if skill is None:
        entry = {"skill_id": skill_id, "from": None, "to": to_state, "ok": False, "reason": "skill_not_found"}
        log.append(entry); return False, "skill_not_found"
    frm = skill["lifecycle_state"]
    if not can_transition(frm, to_state):
        reason = f"illegal_transition:{frm}->{to_state}"
        log.append({"skill_id": skill_id, "from": frm, "to": to_state, "ok": False, "reason": reason})
        return False, reason
    if to_state == "published":
        gate = evaluate_gate(skill)
        if not gate["passed"]:
            reason = "gate_failed:" + ",".join(gate["failures"])
            log.append({"skill_id": skill_id, "from": frm, "to": to_state, "ok": False, "reason": reason})
            return False, reason
    skill["lifecycle_state"] = to_state
    log.append({"skill_id": skill_id, "from": frm, "to": to_state, "ok": True, "reason": "ok"})
    return True, "ok"

def evaluate_gate(skill):
    """Publishing gate. Each rule fails independently with a named reason."""
    failures = []
    if skill.get("contract_check") != "pass":
        failures.append("contract_check_failed")
    ev = skill.get("eval_evidence") or {}
    if not ev.get("present") or ev.get("score") is None:
        failures.append("eval_evidence_missing")
    elif ev.get("threshold") is not None and ev["score"] < ev["threshold"]:
        failures.append("eval_score_below_threshold")
    if not (skill.get("owner") or "").strip():
        failures.append("owner_missing")
    prev = skill.get("previous_published_version")
    if prev is not None and not (_v(skill.get("version")) > _v(prev)):
        failures.append("version_not_increased")
    return {"skill_id": skill.get("id"), "passed": not failures, "failures": sorted(failures)}

def blast_radius(registry, skill_id):
    """Reverse-dependency walk: published skills (transitively) depending
    on skill_id, plus the agents consuming those skills."""
    rev = {}
    for s in registry:
        for dep in s.get("depends_on", []):
            rev.setdefault(dep, []).append(s["id"])
    seen, stack = set(), [skill_id]
    while stack:
        cur = stack.pop()
        for nxt in rev.get(cur, []):
            if nxt not in seen:
                seen.add(nxt); stack.append(nxt)
    affected = sorted(sid for sid in seen
                      if (find_skill(registry, sid) or {}).get("lifecycle_state") == "published")
    agents = sorted({a for sid in affected for a in find_skill(registry, sid).get("consumed_by", [])})
    return {"skill_id": skill_id, "affected_skills": affected, "affected_agents": agents,
            "skill_count": len(affected), "agent_count": len(agents)}

def evaluate_intake(proposal, registry=None):
    """One fixed rubric, 5 criteria x 1 point. adopt=5, wait=3-4, pass=0-2."""
    registry = SKILLS if registry is None else registry
    existing = {s["id"] for s in registry} | {s["name"].lower() for s in registry}
    dup = proposal.get("duplicate_of")
    is_dup = bool(dup) and (dup in existing or str(dup).lower() in existing)
    criteria = {
        "success_criteria_defined": bool(proposal.get("success_criteria_defined")),
        "eval_plan_present": bool(proposal.get("eval_plan_present")),
        "owner_named": bool((proposal.get("owner") or "").strip()),
        "not_duplicate": not is_dup,
        "timebox_within_cap": (proposal.get("timebox_weeks") is not None
                               and proposal["timebox_weeks"] <= TIMEBOX_CAP_WEEKS),
    }
    score = sum(1 for v in criteria.values() if v)
    verdict = "adopt" if score == 5 else ("wait" if score >= 3 else "pass")
    return {"proposal_id": proposal.get("id"), "score": score, "max_score": 5,
            "criteria": criteria, "timebox_weeks": proposal.get("timebox_weeks"),
            "timebox_cap_weeks": TIMEBOX_CAP_WEEKS, "verdict": verdict}

def check_registry(registry):
    """Published skills must satisfy every gate invariant."""
    findings = []
    for s in registry:
        if s.get("lifecycle_state") == "published":
            g = evaluate_gate(s)
            if not g["passed"]:
                findings.append({"skill_id": s["id"], "failures": g["failures"]})
        if s.get("lifecycle_state") not in STATES:
            findings.append({"skill_id": s["id"], "failures": ["unknown_state"]})
        for dep in s.get("depends_on", []):
            if find_skill(registry, dep) is None:
                findings.append({"skill_id": s["id"], "failures": [f"unknown_dependency:{dep}"]})
    return findings
