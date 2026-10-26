"""Guard: no doc may route mounting Kit to another agent (Brendon 2026-10-25)."""
import pathlib, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]

class MountNeverHandoff(unittest.TestCase):
    def test_load_kit_plain_mount(self):
        t = (ROOT / "LOAD_KIT.md").read_text()
        self.assertIn("Never hand mounting to another agent", t)
        self.assertIn("If a step truly cannot run", t)
        self.assertNotIn("Repository development still follows", t)

    def test_routing_docs_exempt_mounting(self):
        b = (ROOT / "PROJECT_BOOTSTRAP.md").read_text()
        step0 = b.split("### 0. Identify the worker", 1)[1][:600]
        self.assertIn("Mounting Kit is exempt", step0)
        a = (ROOT / "coordination/AGENTS_AND_TOOLS.md").read_text()
        contract = a.split("## Execution-routing contract", 1)[1][:800]
        self.assertIn("Not for mounting Kit", contract)

    def test_gpt_instructions_forbid_handoff(self):
        t = (ROOT / "docs/CUSTOM_GPT_SETUP.md").read_text()
        self.assertIn("never hand it to Grok Build or any other agent", t)
        self.assertNotIn("resolve the missing build", t)

if __name__ == "__main__":
    unittest.main()
