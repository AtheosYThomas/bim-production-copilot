"""Create an immutable source-item version for a new isolated WORK run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def version_source_item(source: Path, output: Path, work_run: str) -> dict:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite source-item version: {output}")

    payload = json.loads(source.read_text(encoding="utf-8"))
    old_run = payload["item"]["work_run"]
    if old_run == work_run:
        raise ValueError("new work run must differ from the source version")

    payload["item"]["work_run"] = work_run
    for key, path in payload["modeling_scope"]["output_paths"].items():
        if old_run not in path:
            raise ValueError(f"output path {key!r} is not bound to {old_run!r}")
        payload["modeling_scope"]["output_paths"][key] = path.replace(old_run, work_run)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-run", required=True)
    args = parser.parse_args()
    payload = version_source_item(args.source, args.output, args.work_run)
    print(json.dumps({"item_id": payload["item"]["item_id"], "work_run": args.work_run}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
