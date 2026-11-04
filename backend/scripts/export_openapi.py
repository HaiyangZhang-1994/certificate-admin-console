"""Export or verify the deterministic OpenAPI document without starting a server."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import create_app  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
target = ROOT / "docs" / "api" / "openapi.json"
content = json.dumps(create_app().openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
if args.check:
    if not target.exists() or target.read_text(encoding="utf-8") != content:
        raise SystemExit(
            "OpenAPI drift: coordinate contract changes, then run npm run contract:generate"
        )
    print("OpenAPI matches backend declarations.")
else:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    print(f"Exported {target.relative_to(ROOT)}")
