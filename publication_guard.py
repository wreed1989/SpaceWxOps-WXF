#!/usr/bin/env python3
"""Decide whether generated flare guidance contains a publish-worthy change.

Retrieval and observation timestamps prove that a scheduled check ran, but they
are not forecast revisions.  This module deliberately ignores those volatile
timestamps while comparing forecast content.  Provider-audit comparisons retain
state and transition history, so stopped/resumed events remain publish-worthy.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Mapping


def forecast_content(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return the forecast payload with poll-only timestamps removed."""
    result = copy.deepcopy(dict(payload))
    solar = result.get("solar_monitor")
    if isinstance(solar, dict):
        solar.pop("retrieved_at", None)
    # external_sources is poll diagnostics (HTTP results, catalog snapshots,
    # generated_at, and failure detail), not accepted forecast guidance.  The
    # accepted members live under regions; availability is compared separately
    # through the durable provider audit below.
    result.pop("external_sources", None)
    return result


def provider_state(audit: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return durable provider state and transition history only."""
    if audit is None:
        return None
    providers = audit.get("providers")
    states: dict[str, Any] = {}
    if isinstance(providers, Mapping):
        for key, value in providers.items():
            if isinstance(value, Mapping):
                states[str(key)] = value.get("state")
    events = audit.get("events")
    return {
        "schema_version": audit.get("schema_version"),
        "forecast_issued": audit.get("forecast_issued"),
        "forecast_valid_start": audit.get("forecast_valid_start"),
        "forecast_valid_end": audit.get("forecast_valid_end"),
        "states": states,
        "events": copy.deepcopy(events) if isinstance(events, list) else [],
    }


def publish_worthy_change(
    previous_payload: Mapping[str, Any],
    candidate_payload: Mapping[str, Any],
    previous_audit: Mapping[str, Any] | None = None,
    candidate_audit: Mapping[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if forecast_content(previous_payload) != forecast_content(candidate_payload):
        reasons.append("forecast content changed")
    if provider_state(previous_audit) != provider_state(candidate_audit):
        reasons.append("provider state or transition history changed")
    return bool(reasons), reasons


def _load(path: Path | None) -> Mapping[str, Any] | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-payload", type=Path, required=True)
    parser.add_argument("--candidate-payload", type=Path, required=True)
    parser.add_argument("--previous-audit", type=Path)
    parser.add_argument("--candidate-audit", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)

    changed, reasons = publish_worthy_change(
        _load(args.previous_payload) or {},
        _load(args.candidate_payload) or {},
        _load(args.previous_audit),
        _load(args.candidate_audit),
    )
    message = ", ".join(reasons) if reasons else "retrieval/check metadata only"
    print(f"publish={'true' if changed else 'false'}: {message}")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"publish={'true' if changed else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
