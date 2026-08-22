#!/usr/bin/env python3
"""Final strict multi-source adapter for the SpaceWxOps flare-guidance feed.

Extends the schema-aligned CCMC parser with NASA MAG4.  Sources absent from the
current CCMC catalog or lacking a current valid forecast remain unavailable and
are not replaced by another model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import external_flare_guidance as legacy
import external_flare_guidance_fixed as strict
import external_flare_guidance_strict_v3 as schema_v3

SCRIPT_VERSION = "4.0.0"

PROVIDERS = strict.PROVIDERS + (
    {
        "key": "ccmc_mag4",
        "label": "NASA MAG4",
        "patterns": (
            r"MAG4_LOS_r_FULLDISK",
            r"MAG4.*free energy with flares",
        ),
        "fallback_ids": ("MAG4_LOS_r_FULLDISK",),
    },
)

# Importing the two lower-level adapters installs strict catalog matching and
# schema-aware HAPI decoding. Extend only the provider list here.
legacy.PROVIDERS = PROVIDERS
legacy.provider_dataset = strict.strict_provider_dataset
legacy.fetch_ccmc_catalog = strict.capture_catalog
legacy.fetch_ccmc_member = schema_v3.fetch_ccmc_member


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Add verified SIDC, Met Office, FLARECAST, MagPy, MAG4, DAFFS, "
            "and A-EFFort guidance"
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--js-output", type=Path)
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("payload root must be an object")

        payload = legacy.enrich(payload)
        external = payload.setdefault("external_sources", {})
        external["strict_parser_version"] = SCRIPT_VERSION
        external["availability_policy"] = (
            "Only current, positively identified forecasts are published. "
            "Missing, stale, retired, or maintenance-mode providers remain unavailable."
        )
        external["ccmc_catalog_entries"] = [
            {
                "id": item.get("id"),
                "title": item.get("title", ""),
                "description": item.get("description", ""),
            }
            for item in strict.CATALOG_SNAPSHOT
        ]

        legacy.atomic_write(
            args.output,
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        )
        js_output = args.js_output or args.output.with_name("flare_guidance.js")
        legacy.atomic_write(js_output, legacy.javascript_payload(payload))
        available = sorted(legacy.full_disk_region(payload).get("members", {}).keys())
        print(
            "Strict multi-source guidance update complete; available members: "
            + ", ".join(available)
        )
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
