"""Freeze voice thresholds from a labeled live calibration session (no audio is stored).

Procedure: after enrolling, each volunteer speaks two NEW phrases with push-to-talk, then a
non-enrolled person speaks twice. Then run, giving the true labels in the order spoken:

  .venv/bin/python scripts/calibrate_voice.py emp_asha emp_asha emp_ben emp_ben emp_casey emp_casey unknown unknown

It reads the latest N identification events from Atlas `desk_events` (scores only), prints a
confusion summary under the chosen thresholds, and writes voice_calibration.json.
Add --dry-run to print without writing.
"""

import json
import sys

from march.config import ROOT, settings
from march.db import connect


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    cfg = settings()
    db = connect(cfg, cfg.mode)
    events = list(
        db.desk_events.find(
            {"mode": cfg.mode, "kind": "voice_identification", "diagnostics.scores": {"$ne": {}}}
        )
        .sort("createdAt", -1)
        .limit(len(args))
    )[::-1]
    if len(events) != len(args):
        sys.exit(f"Need {len(args)} scored events, found {len(events)}.")
    genuine, impostor, margins = [], [], []
    for label, event in zip(args, events, strict=True):
        scores = event["diagnostics"]["scores"]
        ranked = sorted(scores.values(), reverse=True)
        if label == "unknown":
            impostor.append(ranked[0])
        else:
            own = scores.get(label)
            if own is None:
                sys.exit(f"{label} has no active profile")
            genuine.append(own)
            others = [v for k, v in scores.items() if k != label]
            impostor.extend(others)
            margins.append(own - (max(others) if others else -1.0))
    lo, hi = max(impostor), min(genuine)
    print(f"genuine scores: {sorted(round(g, 3) for g in genuine)}")
    print(f"impostor/other scores: max {lo:.3f}")
    print(f"genuine margins: min {min(margins):.3f}" if margins else "no genuine samples")
    if hi <= lo:
        print("OVERLAP: genuine and impostor scores overlap; voice ID is not reliable here.")
        accept = round(lo + 0.01, 3)  # Zero false accepts on this set, at the cost of rejects.
    else:
        accept = round(lo + (hi - lo) * 0.5, 3)
    margin = round(min(0.15, max(0.05, min(margins) * 0.5)), 3) if margins else 0.08
    result = {
        "accept": accept,
        "margin": margin,
        "min_voiced_seconds": 1.0,
        "samples": {"genuine": len(genuine), "unknownTrials": args.count("unknown")},
        "separated": hi > lo,
        "maxImpostor": round(lo, 3),
        "minGenuine": round(hi, 3),
    }
    false_accepts = sum(1 for s in impostor if s >= accept)
    false_rejects = sum(1 for s in genuine if s < accept)
    print(f"chosen accept={accept} margin={margin}  ->  on this set: "
          f"false accepts {false_accepts}, false rejects {false_rejects}")
    if not dry:
        (ROOT / "voice_calibration.json").write_text(json.dumps(result, indent=2) + "\n")
        print("wrote voice_calibration.json (restart the server to load it)")


if __name__ == "__main__":
    main()
