#!/usr/bin/env python3
"""Write checksums and sizes for the repository's compact research datasets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parent
    data_root = root / "datasets"
    output = data_root / "manifest.json"
    files = []
    for path in sorted(data_root.iterdir()):
        if not path.is_file() or path == output:
            continue
        files.append(
            {
                "path": str(path.relative_to(root)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    payload = {
        "schema_version": "1.0",
        "note": "Compact, derived, or government-source artifacts only; raw multi-GB archives are intentionally excluded.",
        "files": files,
        "total_bytes": sum(item["bytes"] for item in files),
    }
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
