"""Compile each eval transcript ONCE through the real NovemberAI live compiler and cache it.

The harness under test is MARCH's layer, so baseline and candidate both consume identical
November outputs. Cache files record compiler label and timestamp for provenance.
"""

import json
import sys
from datetime import UTC, datetime

from march.config import ROOT
from march.november_bridge import COMPILE_ERRORS, NovemberCompiler

SUITE = ROOT / "evals/cases/suite_v1.json"
OUT = ROOT / "evals/compiled/suite_v1.november.json"


def main() -> None:
    cases = json.loads(SUITE.read_text())["cases"]
    cache = json.loads(OUT.read_text()) if OUT.is_file() else {}
    compiler = NovemberCompiler("live")
    for case in cases:
        text = case["transcript"]
        if text in cache and "--refresh" not in sys.argv:
            continue
        try:
            out = compiler.compile(text)
        except COMPILE_ERRORS as exc:
            out = {"error": type(exc).__name__, "compiler": compiler.label}
        out["compiledAt"] = datetime.now(UTC).isoformat()
        cache[text] = out
        OUT.write_text(json.dumps(cache, indent=2) + "\n")
        status = out.get("decision", {}).get("status", out.get("error"))
        print(case["id"], status, out.get("intent", {}).get("intent_type"), flush=True)


if __name__ == "__main__":
    main()
