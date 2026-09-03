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


def _restore_wxf_full_disk_union(payload: dict[str, Any]) -> None:
    """Rebuild the WXF disk value from unique regional components.

    Older workflow revisions applied a dominant-region proxy after the base WXF
    forecast was generated. The strict adapter runs later in that workflow, so
    it also acts as a compatibility guard: current model payloads always leave
    this adapter with the same unique-component union produced by inference.
    """
    regions = [row for row in payload.get("regions", []) if isinstance(row, dict)]
    full = next((row for row in regions if row.get("id") == "full-disk"), None)
    if full is None:
        return

    components: dict[str, tuple[float | None, float | None]] = {}
    component_counts: dict[str, int] = {}
    sharp_regions = 0
    fallback_regions = 0
    for row in regions:
        if row is full:
            continue
        member = (row.get("members") or {}).get("sharpmag")
        if not isinstance(member, dict):
            continue
        method = str(member.get("method") or "")
        if method == "sharp_magnetic":
            sharp_regions += 1
        elif method == "morphology_fallback":
            fallback_regions += 1
        values: list[float | None] = []
        for key in ("m1", "x1"):
            try:
                value = float(member.get(key))
            except (TypeError, ValueError):
                value = None
            if value is not None and not 0.0 <= value <= 100.0:
                value = None
            values.append(value)
        component_id = str(member.get("component_id") or row.get("id") or "")
        if component_id:
            component_counts[component_id] = component_counts.get(component_id, 0) + 1
            if component_id not in components:
                components[component_id] = (values[0], values[1])

    # Current payloads preserve the unrounded component probabilities so a
    # downstream compatibility repair reproduces the base inference exactly.
    exact_components = payload.get("wxf_region_components")
    if isinstance(exact_components, list):
        exact: dict[str, tuple[float | None, float | None]] = {}
        for item in exact_components:
            if not isinstance(item, dict):
                continue
            component_id = str(item.get("component_id") or "")
            values = []
            for key in ("m1", "x1"):
                try:
                    value = float(item.get(key))
                except (TypeError, ValueError):
                    value = None
                if value is not None and not 0.0 <= value <= 100.0:
                    value = None
                values.append(value)
            if component_id:
                exact[component_id] = (values[0], values[1])
        if exact:
            components = exact

    def union(index: int) -> float | None:
        probabilities = [
            values[index] / 100.0
            for values in components.values()
            if values[index] is not None
        ]
        if not probabilities:
            return None
        survival = 1.0
        for probability in probabilities:
            survival *= 1.0 - probability
        return round((1.0 - survival) * 100.0, 1)

    m1 = union(0)
    x1 = union(1)
    if m1 is None and x1 is None:
        return
    if m1 is not None and x1 is not None:
        x1 = min(x1, m1)
    full.setdefault("members", {})["sharpmag"] = {
        "m1": m1,
        "x1": x1,
        "source": f"WXF {payload.get('model_version', 'unknown')} regional combination",
        "quality": "operational" if payload.get("operational") else "research",
        "method": "regional_union_with_explicit_fallbacks",
    }
    shared_values = sum(count for count in component_counts.values() if count > 1)
    payload["wxf_full_disk"] = {
        "method": "union_of_unique_region_components",
        "formula": "1 - product(1 - regional probability)",
        "components": len(components),
        "numbered_regions": len([row for row in regions if row is not full]),
        "sharp_regions": sharp_regions,
        "shared_harp_region_values": shared_values,
        "fallback_regions": fallback_regions,
        "unnumbered_or_farside_residual": False,
        "note": (
            "Coverage aggregate, not a separately trained full-disk classifier. "
            "Shared HARP probabilities are included once."
        ),
    }


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
        _restore_wxf_full_disk_union(payload)

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
