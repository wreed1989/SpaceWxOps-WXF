#!/usr/bin/env python3
"""Comprehensive strict multi-source adapter for SpaceWxOps flare guidance.

The adapter publishes every current, positively identified full-disk provider
requested for the operations-wall comparison.  It uses the NASA/CCMC Flare
Scoreboard HAPI feed for participating models, the official SIDC page, and the
official FLARECAST feed.  A source is never replaced with another model and no
probability is invented: unavailable, stale, non-overlapping, retired, or
maintenance-mode products remain absent from ``members`` and are described in
``external_sources`` for the HTML status display.

SpaceWeatherLive and the CCMC NOAA_1 mirror are deliberately excluded because
the wall already displays the primary SWPC forecast directly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import external_flare_guidance as legacy
import external_flare_guidance_fixed as strict
import external_flare_guidance_strict_v3 as schema_v3

SCRIPT_VERSION = "5.0.0"

# Exact dataset identifiers are preferred so similarly named models cannot be
# substituted for one another.  DAFFS and A-EFFort remain configured even when
# they are absent from the current catalog; their status is still recorded.
PROVIDERS: tuple[dict[str, Any], ...] = (
    {
        "key": "sidc",
        "label": "SIDC Operator",
        "patterns": (r"SIDC_Operator_FULLDISK", r"SIDC human operator"),
        "fallback_ids": ("SIDC_Operator_FULLDISK",),
    },
    {
        "key": "metoffice",
        "label": "Met Office (MOSWOC)",
        "patterns": (r"MO_TOT1_FULLDISK", r"Met Office"),
        "fallback_ids": ("MO_TOT1_FULLDISK",),
    },
    {
        "key": "ccmc_amos",
        "label": "CCMC AMOS",
        "patterns": (r"AMOS_v1_FULLDISK",),
        "fallback_ids": ("AMOS_v1_FULLDISK",),
    },
    {
        "key": "ccmc_asap",
        "label": "CCMC ASAP",
        "patterns": (r"ASAP_1_FULLDISK",),
        "fallback_ids": ("ASAP_1_FULLDISK",),
    },
    {
        "key": "ccmc_assa24",
        "label": "CCMC ASSA 24H",
        "patterns": (r"ASSA_24H_1_FULLDISK",),
        "fallback_ids": ("ASSA_24H_1_FULLDISK",),
    },
    {
        "key": "ccmc_assa",
        "label": "CCMC ASSA",
        "patterns": (r"ASSA_1_FULLDISK",),
        "fallback_ids": ("ASSA_1_FULLDISK",),
    },
    {
        "key": "ccmc_bom",
        "label": "BoM Flarecast",
        "patterns": (r"BoM_flare1_FULLDISK", r"Australian Bureau of Meteorology"),
        "fallback_ids": ("BoM_flare1_FULLDISK",),
    },
    {
        "key": "ccmc_mag4_fe",
        "label": "NASA MAG4 Free Energy",
        "patterns": (r"MAG4_LOS_FEr_FULLDISK", r"Free energy only"),
        "fallback_ids": ("MAG4_LOS_FEr_FULLDISK",),
    },
    {
        "key": "ccmc_mag4",
        "label": "NASA MAG4",
        "patterns": (r"MAG4_LOS_r_FULLDISK", r"Free energy with flares"),
        "fallback_ids": ("MAG4_LOS_r_FULLDISK",),
    },
    {
        "key": "ccmc_magpy_los",
        "label": "CCMC MagPy HMI LOS",
        "patterns": (r"MagPy-HMI-LOS_FULLDISK",),
        "fallback_ids": ("MagPy-HMI-LOS_FULLDISK",),
    },
    {
        "key": "ccmc_magpy",
        "label": "CCMC MagPy SHARP",
        "patterns": (r"MagPy_SHARP_HMI_CEA_FULLDISK",),
        "fallback_ids": ("MagPy_SHARP_HMI_CEA_FULLDISK",),
    },
    {
        "key": "ccmc_sps",
        "label": "CCMC SPS",
        "patterns": (r"SPS_FULLDISK", r"SPS Flare Scoreboard"),
        "fallback_ids": ("SPS_FULLDISK",),
    },
    {
        "key": "ccmc_daffs",
        "label": "CCMC DAFFS",
        "patterns": (r"\bDAFFS\b", r"Discriminant Analysis Flare"),
        "fallback_ids": (),
    },
    {
        "key": "ccmc_aeffort",
        "label": "CCMC A-EFFort",
        "patterns": (r"A[-_ ]?EFFort", r"Athens Effective Solar Flare"),
        "fallback_ids": (),
    },
)

# Importing the lower-level adapters installs provider-specific catalog matching
# and schema-aware HAPI decoding.  Replace the provider list with the complete
# set above rather than extending it, which prevents duplicate MagPy/MAG4 rows.
legacy.PROVIDERS = PROVIDERS
legacy.provider_dataset = strict.strict_provider_dataset
legacy.fetch_ccmc_catalog = strict.capture_catalog
legacy.fetch_ccmc_member = schema_v3.fetch_ccmc_member


def _provider_status_key(provider_key: str) -> str:
    """Return the status key produced by legacy.enrich for a provider."""
    return f"ccmc_{provider_key}"


def _prune_unverified_members(payload: dict[str, Any]) -> None:
    """Remove a carried member unless this run positively validated it."""
    full = legacy.full_disk_region(payload)
    members = full.setdefault("members", {})
    external = payload.get("external_sources")
    if not isinstance(external, dict):
        external = {}

    for provider in PROVIDERS:
        key = str(provider["key"])
        if key == "sidc" and isinstance(external.get("sidc_direct"), dict):
            if external["sidc_direct"].get("ok"):
                continue
        status = external.get(_provider_status_key(key))
        if not (isinstance(status, dict) and status.get("ok")):
            members.pop(key, None)

    flarecast_status = external.get("flarecast")
    if not (isinstance(flarecast_status, dict) and flarecast_status.get("ok")):
        members.pop("flarecast", None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Add verified SIDC, Met Office, FLARECAST, and all current requested "
            "NASA/CCMC full-disk flare-probability guidance"
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
        _prune_unverified_members(payload)

        external = payload.setdefault("external_sources", {})
        external["strict_parser_version"] = SCRIPT_VERSION
        external["availability_policy"] = (
            "Only current, positively identified forecasts that overlap the wall's "
            "target period are published. Missing, stale, retired, maintenance-mode, "
            "or non-overlapping providers remain unavailable rather than being "
            "replaced or assigned a synthetic probability."
        )
        external["provider_catalog"] = [
            {
                "key": provider["key"],
                "label": provider["label"],
                "dataset_ids": list(provider.get("fallback_ids", ())),
            }
            for provider in PROVIDERS
        ] + [
            {
                "key": "flarecast",
                "label": "FLARECAST",
                "dataset_ids": [],
            },
            {
                "key": "njit_solarflarenet",
                "label": "NJIT SolarFlareNet",
                "dataset_ids": [],
                "status": "web-product-only",
            },
            {
                "key": "inaf_oact",
                "label": "INAF-OACT",
                "dataset_ids": [],
                "status": "web-product-only",
            },
        ]
        external["njit_solarflarenet"] = {
            "ok": False,
            "label": "NJIT SolarFlareNet",
            "url": "https://nature.njit.edu/solardb/index.html",
            "detail": (
                "The public SolarDB tool is retained in the wall's source inventory, "
                "but this workflow has no stable unauthenticated machine-readable "
                "endpoint from which to reproduce its current probabilities."
            ),
        }
        external["inaf_oact"] = {
            "ok": False,
            "label": "INAF-OACT",
            "url": "http://ssa.oact.inaf.it/oact/Flare_forecasting.php",
            "detail": (
                "The OACT web product is retained in the wall's source inventory, "
                "but no stable current machine-readable feed is configured."
            ),
        }
        external["excluded_duplicates"] = {
            "spaceweatherlive": (
                "Intentionally excluded because it republishes operational SWPC "
                "probabilities already displayed by the wall."
            ),
            "NOAA_1_FULLDISK": (
                "Intentionally excluded from the CCMC rows because the primary SWPC "
                "forecast already appears as its own method."
            ),
        }
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
            "Comprehensive strict multi-source guidance update complete; "
            "available members: " + ", ".join(available)
        )
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
