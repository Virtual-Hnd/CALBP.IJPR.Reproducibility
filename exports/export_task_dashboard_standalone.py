#!/usr/bin/env python3
"""Export the current task-based DOE dashboard as a standalone HTML file."""

from __future__ import annotations

import json
import os
import zipfile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import scripts.dashboard as dashboard
RESULTS_DIR = Path(
    os.environ.get(
        "RESULTS_DIR",
        ROOT / "published_results" / "l9_task_progress_220of252_2026-05-13_19-21-43",
    )
).expanduser()
OUT_DIR = Path(os.environ.get("OUT_DIR", ROOT / "exports")).expanduser()
HTML_OUT = OUT_DIR / os.environ.get(
    "HTML_OUT", "calbp_dashboard_task_l9_252_standalone.html"
)
ZIP_OUT = OUT_DIR / os.environ.get(
    "ZIP_OUT", "calbp_dashboard_task_l9_252_standalone.zip"
)


def build_html() -> tuple[str, dict]:
    dashboard.RESULTS_DIR = RESULTS_DIR
    dashboard.SOLUTIONS_DIR = RESULTS_DIR / "solutions"
    payload = dashboard.scan_results()
    data_json = json.dumps(payload, default=str)
    html = dashboard.HTML_PAGE.replace(
        "<script>\nconst MODES",
        "<script>\n"
        f"window.__DASHBOARD_STATIC_DATA__ = {data_json};\n"
        "const MODES",
        1,
    )
    html = html.replace(
        "fetchData();\nif (!window.__DASHBOARD_STATIC_DATA__) startRefresh();",
        "fetchData();\n// Static standalone export: no server/API needed.",
    )
    html = html.replace("All (45)", "All")
    html = html.replace("Scholl (14)", "Scholl")
    html = html.replace("Otto (14)", "Otto")
    return html, payload


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html, payload = build_html()
    HTML_OUT.write_text(html, encoding="utf-8")
    with zipfile.ZipFile(ZIP_OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(HTML_OUT, arcname=HTML_OUT.name)
    print(f"[standalone-export] results_dir={RESULTS_DIR}")
    print(f"[standalone-export] summary={payload['summary']}")
    print(f"[standalone-export] html={HTML_OUT}")
    print(f"[standalone-export] zip={ZIP_OUT}")


if __name__ == "__main__":
    main()
