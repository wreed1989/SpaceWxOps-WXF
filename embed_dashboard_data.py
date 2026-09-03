#!/usr/bin/env python3
"""Refresh the standalone dashboard's offline WXF payload and model report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    left = text.find(start)
    if left < 0:
        raise SystemExit(f"Start marker not found: {start!r}")
    right = text.find(end, left + len(start))
    if right < 0:
        raise SystemExit(f"End marker not found after {start!r}")
    return text[:left] + replacement + text[right + len(end) :]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--forecast", type=Path, default=Path("flare_guidance.json"))
    parser.add_argument("--training-report", type=Path, default=Path("sharp_mag_training_report.json"))
    args = parser.parse_args()

    forecast = json.loads(args.forecast.read_text(encoding="utf-8"))
    report = json.loads(args.training_report.read_text(encoding="utf-8"))
    text = args.html.read_text(encoding="utf-8")
    text = replace_between(
        text,
        "  window.FLARE_GUIDANCE_PAYLOAD = ",
        ";\n  </script>",
        "  window.FLARE_GUIDANCE_PAYLOAD = "
        + json.dumps(forecast, indent=2, sort_keys=False)
        + ";\n  </script>",
    )
    report_start = "  const WXF_TRAINING_REPORT_FALLBACK = Object.freeze("
    next_block = "\n\n  const WXF_SDO_DATASET_AUDIT = Object.freeze("
    left = text.find(report_start)
    right = text.find(next_block, left + len(report_start))
    if left < 0 or right < 0:
        raise SystemExit("Training-report block markers were not found")
    text = (
        text[:left]
        + report_start
        + json.dumps(report, indent=2, sort_keys=False)
        + "\n  );"
        + text[right:]
    )
    args.html.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
