"""Run the evaluation suite or one improvement cycle against march_eval (fixture-only).

  .venv/bin/python scripts/run_eval.py baseline            # active version, all splits, once
  .venv/bin/python scripts/run_eval.py cycle emp_asha      # one bounded improvement cycle
"""

import json
import sys

from march.config import settings
from march.db import Store, connect
from march.evaluation import EVAL_CLOCK, run_suite, seed_memories, wait_for_index
from march.fixtures import seed
from march.harness import Harness
from march.improve import run_cycle
from march.orchestrator import Orchestrator


class NoCompiler:
    label = "cached_november_outputs_only"

    def compile(self, text: str) -> dict:
        raise RuntimeError("evaluation must use cached November outputs")


def main() -> None:
    cfg = settings()
    demo, ev = Store(connect(cfg, "demo")), Store(connect(cfg, "eval"))
    seed(ev.db, "eval", cfg.org_id)
    orch = Orchestrator(ev, NoCompiler(), clock=lambda: EVAL_CLOCK)
    if sys.argv[1] == "baseline":
        version = Harness(demo.db, "demo", cfg.org_id).active(sys.argv[2] if len(sys.argv) > 2 else "emp_asha")
        orch.recall_cache = {}
        import os
        suite = os.getenv("MARCH_SUITE", "suite_v2")
        seed_memories(ev, cfg.org_id, suite)
        print(suite, "index synced:", wait_for_index(ev, cfg.org_id, suite=suite))
        out = run_suite(ev, orch, cfg.org_id, version, ("dev", "val", "test"))
        print(version["_id"], out["bySplit"], "critical failures:", out["criticalFailures"], "invalid recall:", out["invalidRecallCases"])
        for r in out["results"]:
            if not r["pass"]:
                print(" FAIL", r["id"], r["split"], r["failures"], "prefsUsed=", r.get("preferencesUsed"))
    else:
        record = run_cycle(demo, ev, orch, cfg.org_id, sys.argv[2])
        print(json.dumps({k: record.get(k) for k in ("_id", "gateDecision", "failureCodes", "proposal", "aggregate", "heldOutTest")}, indent=2, default=str))


if __name__ == "__main__":
    main()
