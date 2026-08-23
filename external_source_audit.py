#!/usr/bin/env python3
"""Persist availability transitions for external flare-guidance providers.

The flare payload intentionally contains only forecasts that are current and
overlap its valid window.  This companion ledger retains provider availability
across refreshes so an operations user can distinguish a continuing outage from
a newly stopped or newly resumed model without ever displaying stale values.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

UTC = dt.timezone.utc
SCHEMA_VERSION = 1
MAX_PROVIDER_TRANSITIONS = 100
MAX_GLOBAL_EVENTS = 1000


def iso_z(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_time(value: str | None) -> dt.datetime:
    if not value:
        return dt.datetime.now(tz=UTC)
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def atomic_write(path: Path, text: str) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def full_disk_members(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    regions = payload.get("regions")
    if not isinstance(regions, list):
        return {}
    for region in regions:
        if not isinstance(region, Mapping):
            continue
        if str(region.get("id", "")).lower() != "full-disk":
            continue
        members = region.get("members")
        return members if isinstance(members, Mapping) else {}
    return {}


def member_has_probability(member: Any) -> bool:
    if not isinstance(member, Mapping):
        return False
    for key in ("m1", "x1", "m", "x"):
        try:
            number = float(member.get(key))
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and 0 <= number <= 100:
            return True
    return False


def provider_catalog(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    external = payload.get("external_sources")
    if not isinstance(external, Mapping):
        return []
    catalog = external.get("provider_catalog")
    if not isinstance(catalog, list):
        return []
    return [dict(item) for item in catalog if isinstance(item, Mapping) and item.get("key")]


def provider_status(
    external: Mapping[str, Any], provider_key: str
) -> tuple[str | None, Mapping[str, Any] | None]:
    candidates: list[str]
    if provider_key == "sidc":
        candidates = ["sidc_direct", "ccmc_sidc", "sidc"]
    elif provider_key == "flarecast":
        candidates = ["flarecast"]
    else:
        candidates = [f"ccmc_{provider_key}", provider_key]
    found: list[tuple[str, Mapping[str, Any]]] = []
    for key in candidates:
        status = external.get(key)
        if isinstance(status, Mapping):
            found.append((key, status))
    for key, status in found:
        if status.get("ok"):
            return key, status
    if found:
        return found[0]
    return None, None


def transition_kind(previous_state: str | None, current_state: str) -> str:
    if previous_state is None:
        return f"observed_{current_state}"
    if previous_state == "available" and current_state == "unavailable":
        return "stopped"
    if previous_state == "unavailable" and current_state == "available":
        return "resumed"
    return "unchanged"


def update_audit(
    payload: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
    *,
    checked_at: dt.datetime,
) -> dict[str, Any]:
    checked = iso_z(checked_at)
    prior = dict(previous or {})
    prior_providers = prior.get("providers")
    if not isinstance(prior_providers, Mapping):
        prior_providers = {}
    prior_events = prior.get("events")
    events = list(prior_events) if isinstance(prior_events, list) else []

    external = payload.get("external_sources")
    if not isinstance(external, Mapping):
        external = {}
    members = full_disk_members(payload)
    providers: dict[str, Any] = {
        str(key): dict(value)
        for key, value in prior_providers.items()
        if isinstance(value, Mapping)
    }

    for definition in provider_catalog(payload):
        key = str(definition["key"])
        label = str(definition.get("label") or key)
        member = members.get(key)
        status_key, status = provider_status(external, key)
        # The strict adapter prunes every member it did not positively validate,
        # making accepted member presence the canonical availability signal.
        # Status objects remain diagnostic and may contain multiple direct/HAPI
        # attempts for the same provider.
        available = member_has_probability(member)
        state = "available" if available else "unavailable"
        prior_entry = providers.get(key) if isinstance(providers.get(key), Mapping) else {}
        previous_state = str(prior_entry.get("state") or "") or None
        kind = transition_kind(previous_state, state)
        detail = ""
        if isinstance(status, Mapping):
            detail = str(status.get("detail") or "")
        if not detail:
            detail = (
                "Current overlapping probability accepted"
                if available
                else "No current overlapping probability accepted"
            )

        entry = dict(prior_entry)
        entry.update(
            {
                "key": key,
                "label": label,
                "state": state,
                "last_checked": checked,
                "status_key": status_key,
                "detail": detail,
                "dataset_ids": list(definition.get("dataset_ids") or []),
            }
        )
        if not entry.get("first_seen_at"):
            entry["first_seen_at"] = checked
        if kind != "unchanged":
            entry["since"] = checked
            entry["last_changed_at"] = checked

        if available:
            entry["last_available_at"] = checked
            if isinstance(member, Mapping):
                entry["latest_forecast"] = {
                    field: member.get(field)
                    for field in (
                        "m1",
                        "x1",
                        "issued",
                        "valid_start",
                        "valid_end",
                        "dataset_id",
                        "source",
                    )
                    if member.get(field) is not None
                }
        else:
            entry["last_unavailable_at"] = checked

        transitions = entry.get("transitions")
        transitions = list(transitions) if isinstance(transitions, list) else []
        if kind != "unchanged":
            event = {
                "at": checked,
                "provider": key,
                "label": label,
                "event": kind,
                "from": previous_state,
                "to": state,
                "detail": detail,
            }
            transitions.append(event)
            events.append(event)
        entry["transitions"] = transitions[-MAX_PROVIDER_TRANSITIONS:]
        providers[key] = entry

    available_keys = sorted(
        key for key, value in providers.items() if value.get("state") == "available"
    )
    unavailable_keys = sorted(
        key for key, value in providers.items() if value.get("state") == "unavailable"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": checked,
        "forecast_issued": payload.get("issued"),
        "forecast_valid_start": payload.get("valid_start"),
        "forecast_valid_end": payload.get("valid_end"),
        "summary": {
            "available": len(available_keys),
            "unavailable": len(unavailable_keys),
            "available_providers": available_keys,
            "unavailable_providers": unavailable_keys,
        },
        "providers": providers,
        "events": events[-MAX_GLOBAL_EVENTS:],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record external flare-provider availability transitions")
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path, default=Path("external_source_audit.json"))
    parser.add_argument("--checked-at", help="Override the UTC observation time; intended for testing")
    args = parser.parse_args(argv)

    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("payload root must be an object")
    previous: Mapping[str, Any] | None = None
    if args.audit_output.exists():
        loaded = json.loads(args.audit_output.read_text(encoding="utf-8"))
        if isinstance(loaded, Mapping):
            previous = loaded
    audit = update_audit(payload, previous, checked_at=parse_time(args.checked_at))
    atomic_write(args.audit_output, json.dumps(audit, indent=2, ensure_ascii=False) + "\n")
    summary = audit["summary"]
    latest_events = [
        event
        for event in audit["events"]
        if event.get("at") == audit["updated_at"]
    ]
    print(
        "External-source audit updated: "
        f"{summary['available']} available, {summary['unavailable']} unavailable; "
        f"transitions={len(latest_events)}"
    )
    for event in latest_events:
        print(f"  {event['event']}: {event['provider']} ({event['detail']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
