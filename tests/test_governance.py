import copy, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import governance as gov

def reg_with_state(sid, state):
    reg = gov.seed_registry()
    gov.find_skill(reg, sid)["lifecycle_state"] = state
    return reg

class TestTransitions(unittest.TestCase):
    def test_draft_to_in_review(self):
        reg = reg_with_state("calendar-helper", "draft"); log = []
        ok, _ = gov.transition(reg, "calendar-helper", "in_review", log=log); self.assertTrue(ok)
    def test_in_review_to_draft(self):
        reg = reg_with_state("calendar-helper", "in_review"); log = []
        ok, _ = gov.transition(reg, "calendar-helper", "draft", log=log); self.assertTrue(ok)
    def test_published_to_deprecated(self):
        reg = gov.seed_registry(); log = []
        ok, _ = gov.transition(reg, "calendar-helper", "deprecated", log=log); self.assertTrue(ok)
    def test_deprecated_to_retired(self):
        reg = gov.seed_registry(); log = []
        ok, _ = gov.transition(reg, "legacy-parser", "retired", log=log); self.assertTrue(ok)
    def test_in_review_to_published_clean(self):
        reg = gov.seed_registry(); s = gov.find_skill(reg, "version-stalled")
        s["version"] = "1.1.0"; log = []
        ok, _ = gov.transition(reg, "version-stalled", "published", log=log); self.assertTrue(ok)
    def test_draft_to_published_illegal(self):
        reg = reg_with_state("calendar-helper", "draft"); log = []
        ok, r = gov.transition(reg, "calendar-helper", "published", log=log); self.assertFalse(ok); self.assertIn("illegal_transition", r)
    def test_retired_to_anything_illegal(self):
        reg = reg_with_state("calendar-helper", "retired"); log = []
        ok, _ = gov.transition(reg, "calendar-helper", "draft", log=log); self.assertFalse(ok)
    def test_published_to_draft_illegal(self):
        reg = gov.seed_registry(); log = []
        ok, _ = gov.transition(reg, "calendar-helper", "draft", log=log); self.assertFalse(ok)
    def test_published_to_in_review_illegal(self):
        reg = gov.seed_registry(); log = []
        ok, _ = gov.transition(reg, "calendar-helper", "in_review", log=log); self.assertFalse(ok)
    def test_deprecated_to_published_illegal(self):
        reg = gov.seed_registry(); log = []
        ok, _ = gov.transition(reg, "legacy-parser", "published", log=log); self.assertFalse(ok)
    def test_in_review_to_deprecated_illegal(self):
        reg = reg_with_state("calendar-helper", "in_review"); log = []
        ok, _ = gov.transition(reg, "calendar-helper", "deprecated", log=log); self.assertFalse(ok)
    def test_draft_to_retired_illegal(self):
        reg = reg_with_state("calendar-helper", "draft"); log = []
        ok, _ = gov.transition(reg, "calendar-helper", "retired", log=log); self.assertFalse(ok)
    def test_illegal_is_logged(self):
        reg = reg_with_state("calendar-helper", "draft"); log = []
        gov.transition(reg, "calendar-helper", "published", log=log)
        self.assertEqual(len(log), 1); self.assertFalse(log[0]["ok"])
    def test_unknown_skill_logged(self):
        log = []; ok, r = gov.transition(gov.seed_registry(), "nope", "draft", log=log)
        self.assertFalse(ok); self.assertEqual(r, "skill_not_found"); self.assertEqual(len(log), 1)
    def test_gate_blocked_publish_logged(self):
        reg = gov.seed_registry(); log = []
        ok, r = gov.transition(reg, "ownerless-plugin", "published", log=log)
        self.assertFalse(ok); self.assertIn("gate_failed", r); self.assertFalse(log[-1]["ok"])
        self.assertEqual(gov.find_skill(reg, "ownerless-plugin")["lifecycle_state"], "in_review")

class TestGate(unittest.TestCase):
    def setUp(self): self.reg = gov.seed_registry()
    def gate(self, sid): return gov.evaluate_gate(gov.find_skill(self.reg, sid))
    def test_clean_passes(self): self.assertTrue(self.gate("core-retrieval")["passed"])
    def test_owner_missing(self): self.assertEqual(self.gate("ownerless-plugin")["failures"], ["owner_missing"])
    def test_contract_failed(self): self.assertEqual(self.gate("contract-broken")["failures"], ["contract_check_failed"])
    def test_eval_missing(self): self.assertEqual(self.gate("eval-missing")["failures"], ["eval_evidence_missing"])
    def test_eval_low(self): self.assertEqual(self.gate("eval-low")["failures"], ["eval_score_below_threshold"])
    def test_version_not_increased(self): self.assertEqual(self.gate("version-stalled")["failures"], ["version_not_increased"])
    def test_version_equal_fails(self):
        s = gov.find_skill(self.reg, "calendar-helper"); s["version"] = s["previous_published_version"]
        self.assertIn("version_not_increased", gov.evaluate_gate(s)["failures"])
    def test_version_higher_passes(self):
        s = gov.find_skill(self.reg, "version-stalled"); s["version"] = "2.0.0"
        self.assertTrue(gov.evaluate_gate(s)["passed"])
    def test_eval_at_threshold_passes(self):
        s = gov.find_skill(self.reg, "eval-low"); s["eval_evidence"]["score"] = 0.85
        self.assertTrue(gov.evaluate_gate(s)["passed"])
    def test_multiple_failures_all_named(self):
        s = gov.find_skill(self.reg, "ownerless-plugin"); s["contract_check"] = "fail"
        f = gov.evaluate_gate(s)["failures"]
        self.assertIn("owner_missing", f); self.assertIn("contract_check_failed", f)
    def test_first_publish_no_prev_version_ok(self):
        s = gov.find_skill(self.reg, "contract-broken"); s["contract_check"] = "pass"
        self.assertTrue(gov.evaluate_gate(s)["passed"])

class TestBlast(unittest.TestCase):
    def setUp(self): self.reg = gov.seed_registry()
    def test_hub_skills_exact(self):
        self.assertEqual(gov.blast_radius(self.reg, "core-retrieval")["affected_skills"], gov.HUB_BLAST_SKILLS)
    def test_hub_agents_exact(self):
        self.assertEqual(gov.blast_radius(self.reg, "core-retrieval")["affected_agents"], gov.HUB_BLAST_AGENTS)
    def test_hub_counts(self):
        r = gov.blast_radius(self.reg, "core-retrieval"); self.assertEqual((r["skill_count"], r["agent_count"]), (7, 6))
    def test_deprecated_excluded(self):
        self.assertNotIn("legacy-parser", gov.blast_radius(self.reg, "core-retrieval")["affected_skills"])
    def test_leaf_empty(self):
        self.assertEqual(gov.blast_radius(self.reg, "executive-brief")["affected_skills"], [])
    def test_mid_chain(self):
        r = gov.blast_radius(self.reg, "doc-summarizer")
        self.assertEqual(r["affected_skills"], ["briefing-builder", "email-drafter", "executive-brief"])
    def test_hub_not_in_own_radius(self):
        self.assertNotIn("core-retrieval", gov.blast_radius(self.reg, "core-retrieval")["affected_skills"])

class TestIntake(unittest.TestCase):
    def setUp(self): self.reg = gov.seed_registry(); self.props = {p["id"]: p for p in gov.seed_proposals()}
    def verdict(self, pid): return gov.evaluate_intake(self.props[pid], self.reg)
    def test_adopt_a(self): self.assertEqual(self.verdict("prop-adopt-a")["verdict"], "adopt")
    def test_adopt_b(self): self.assertEqual(self.verdict("prop-adopt-b")["verdict"], "adopt")
    def test_wait_a(self): self.assertEqual(self.verdict("prop-wait-a")["verdict"], "wait")
    def test_wait_b(self): self.assertEqual(self.verdict("prop-wait-b")["verdict"], "wait")
    def test_pass_a(self): self.assertEqual(self.verdict("prop-pass-a")["verdict"], "pass")
    def test_pass_b(self): self.assertEqual(self.verdict("prop-pass-b")["verdict"], "pass")
    def test_timebox_recorded(self): self.assertEqual(self.verdict("prop-pass-a")["timebox_weeks"], 8)
    def test_timebox_cap_is_four(self): self.assertEqual(self.verdict("prop-adopt-a")["timebox_cap_weeks"], 4)
    def test_perfect_score_is_five(self): self.assertEqual(self.verdict("prop-adopt-a")["score"], 5)
    def test_duplicate_criterion_false_for_clone(self):
        self.assertFalse(self.verdict("prop-pass-a")["criteria"]["not_duplicate"])
    def test_verdict_counts(self):
        vs = [gov.evaluate_intake(p, self.reg)["verdict"] for p in gov.seed_proposals()]
        self.assertEqual((vs.count("adopt"), vs.count("wait"), vs.count("pass")), (2, 2, 2))

class TestRegistry(unittest.TestCase):
    def test_seed_has_15_skills(self): self.assertEqual(len(gov.seed_registry()), 15)
    def test_check_clean(self): self.assertEqual(gov.check_registry(gov.seed_registry()), [])
    def test_check_catches_bad_published(self):
        reg = gov.seed_registry(); gov.find_skill(reg, "calendar-helper")["owner"] = ""
        self.assertTrue(gov.check_registry(reg))
    def test_ids_unique(self):
        ids = [s["id"] for s in gov.seed_registry()]; self.assertEqual(len(ids), len(set(ids)))
    def test_all_deps_exist(self):
        reg = gov.seed_registry()
        for s in reg:
            for d in s["depends_on"]: self.assertIsNotNone(gov.find_skill(reg, d))
    def test_seed_is_deep_copy(self):
        a = gov.seed_registry(); a[0]["owner"] = "X"
        self.assertNotEqual(gov.seed_registry()[0]["owner"], "X")
    def test_published_all_pass_gate(self):
        for s in gov.seed_registry():
            if s["lifecycle_state"] == "published": self.assertTrue(gov.evaluate_gate(s)["passed"], s["id"])

if __name__ == "__main__":
    unittest.main()
