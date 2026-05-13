#!/usr/bin/env python3
"""
export_archive_dashboard_standalone.py — Build a self-contained dashboard bundle
for the upgraded archive snapshots.

The resulting folder contains:
- the current `dashboard.py`
- the archive snapshots already upgraded to the new result schema
- a simple launcher script to pick which campaign to visualize

Usage
-----
    python scripts/export_archive_dashboard_standalone.py
    python scripts/export_archive_dashboard_standalone.py \
        --source-bundle published_results/archive_v1_newformat_2026-05-13
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def write_text(path: Path, content: str) -> None:
    """Write UTF-8 text, creating parent folders when needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_dashboard_template() -> str:
    """Load the current dashboard HTML template from `scripts/dashboard.py`."""
    dashboard_path = PROJECT_ROOT / "scripts" / "dashboard.py"
    spec = importlib.util.spec_from_file_location("dashboard_template", dashboard_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.HTML_PAGE


def build_static_dashboard_html(template: str, payload: dict, title: str) -> str:
    """Embed one dashboard payload directly into a standalone HTML page."""
    static_script = (
        "<script>\n"
        "window.__DASHBOARD_STATIC_DATA__ = "
        + json.dumps(payload, ensure_ascii=True)
        + ";\n"
        "</script>\n"
    )
    html = template.replace(
        "<title>DOE — Dashboard</title>",
        f"<title>{title}</title>",
        1,
    )
    return html.replace("</head>", static_script + "</head>", 1)


def build_multi_dashboard_html(
    template: str,
    payloads: dict[str, dict],
    title: str,
) -> str:
    """Embed multiple campaign payloads into one standalone dashboard page."""
    campaign_names = sorted(payloads)
    default_name = campaign_names[0]
    static_script = (
        "<script>\n"
        "window.__DASHBOARD_MULTI_DATA__ = "
        + json.dumps(payloads, ensure_ascii=True)
        + ";\n"
        f"window.__DASHBOARD_STATIC_DATA__ = window.__DASHBOARD_MULTI_DATA__[{json.dumps(default_name)}];\n"
        f"window.__DASHBOARD_ACTIVE_CAMPAIGN__ = {json.dumps(default_name)};\n"
        "</script>\n"
    )
    control_script = """<script>
(function () {
  const payloads = window.__DASHBOARD_MULTI_DATA__ || null;
  if (!payloads) return;

  function optionLabel(name) {
    const data = payloads[name] || {};
    const summary = data.summary || {};
    const done = summary.successful ?? summary.completed ?? 0;
    const total = data.total_expected ?? done;
    return `${name} (${done}/${total})`;
  }

  function setCampaign(name) {
    if (!payloads[name]) return;
    window.__DASHBOARD_ACTIVE_CAMPAIGN__ = name;
    window.__DASHBOARD_STATIC_DATA__ = payloads[name];
    document.title = 'Archive Dashboard — ' + name;
    const subtitle = document.querySelector('header h1 span');
    if (subtitle) subtitle.textContent = '— ' + name;
    if (typeof closeSidebar === 'function') closeSidebar();
    if (typeof sourceFilter !== 'undefined') sourceFilter = 'all';
    document.querySelectorAll('.src-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.src === 'all');
    });
    if (typeof fetchData === 'function') fetchData();
  }

  function mountSelector() {
    const hdrRight = document.querySelector('.hdr-right');
    if (!hdrRight) return;

    const wrap = document.createElement('label');
    wrap.style.gap = '8px';
    wrap.style.flexWrap = 'wrap';
    wrap.style.alignItems = 'center';
    wrap.innerHTML = '<span>Campaign</span>';

    const select = document.createElement('select');
    select.id = 'campaign-select';
    select.style.padding = '5px 10px';
    select.style.borderRadius = '6px';
    select.style.border = '1px solid rgba(255,255,255,.35)';
    select.style.background = 'rgba(255,255,255,.12)';
    select.style.color = '#fff';
    select.style.fontSize = '.82rem';

    Object.keys(payloads).sort().forEach(name => {
      const option = document.createElement('option');
      option.value = name;
      option.textContent = optionLabel(name);
      option.style.color = '#0f172a';
      select.appendChild(option);
    });

    select.value = window.__DASHBOARD_ACTIVE_CAMPAIGN__ || Object.keys(payloads)[0];
    select.addEventListener('change', () => setCampaign(select.value));
    wrap.appendChild(select);
    hdrRight.insertBefore(wrap, hdrRight.firstChild);
    setCampaign(select.value);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mountSelector);
  } else {
    mountSelector();
  }
})();
</script>
"""
    html = template.replace(
        "<title>DOE — Dashboard</title>",
        f"<title>{title}</title>",
        1,
    )
    html = html.replace("</head>", static_script + "</head>", 1)
    return html.replace("</body>", control_script + "\n</body>", 1)


def build_launcher(output_dir: Path) -> None:
    """Create a small shell launcher for the standalone dashboard."""
    script = """#!/bin/bash
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_ROOT="$ROOT/results"
CAMPAIGN="${1:-results_doe_scholl_l9}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8050}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d "$RESULTS_ROOT/$CAMPAIGN" ]; then
  echo "Unknown campaign: $CAMPAIGN"
  echo ""
  echo "Available campaigns:"
  find "$RESULTS_ROOT" -maxdepth 1 -mindepth 1 -type d -exec basename {} \\; | sort
  exit 1
fi

echo "[dashboard] campaign=$CAMPAIGN"
echo "[dashboard] url=http://$HOST:$PORT/"
DOE_RESULTS_DIR="$RESULTS_ROOT/$CAMPAIGN" \\
  "$PYTHON_BIN" "$ROOT/dashboard.py" --host "$HOST" --port "$PORT" --no-open
"""
    write_text(output_dir / "launch_dashboard.sh", script)
    (output_dir / "launch_dashboard.sh").chmod(0o755)

    command = """#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/launch_dashboard.sh" "$@"
"""
    write_text(output_dir / "launch_dashboard.command", command)
    (output_dir / "launch_dashboard.command").chmod(0o755)


def build_index_html(output_dir: Path, campaigns: list[str]) -> None:
    """Create a tiny local index page that links to each standalone HTML."""
    items = "\n".join(
        (
            f'<li><a href="html/{name}.html">{name}</a></li>'
            for name in campaigns
        )
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Archive Dashboard HTML</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 40px auto;
      max-width: 900px;
      padding: 0 20px;
      background: #f8fafc;
      color: #0f172a;
    }}
    .card {{
      background: #fff;
      border: 1px solid #e2e8f0;
      border-radius: 14px;
      padding: 24px;
      box-shadow: 0 4px 20px rgba(15, 23, 42, 0.06);
    }}
    h1 {{ margin-top: 0; }}
    ul {{ line-height: 1.9; }}
    a {{ color: #1d4ed8; text-decoration: none; font-weight: 600; }}
    a:hover {{ text-decoration: underline; }}
    code {{
      background: #eef2ff;
      padding: 2px 6px;
      border-radius: 6px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Archive Dashboard HTML</h1>
    <p>Standalone HTML exports for the upgraded archive snapshots.</p>
    <p><a href="html/all_campaigns.html">Open the unified dashboard with all campaigns</a></p>
    <ul>
      {items}
    </ul>
    <p>You can also launch the live Python server version with <code>./launch_dashboard.sh &lt;campaign&gt;</code>.</p>
  </div>
</body>
</html>
"""
    write_text(output_dir / "index.html", html)


def build_readme(output_dir: Path, source_bundle: Path, campaigns: list[str]) -> None:
    """Create the top-level README for the standalone dashboard bundle."""
    campaign_list = "\n".join(f"- `{name}`" for name in campaigns)
    text = f"""# Archive Dashboard Standalone

This folder is a self-contained dashboard bundle for the upgraded archive
snapshots.

## Included campaigns

{campaign_list}

## Launch

From a terminal:

```bash
cd "{output_dir}"
./launch_dashboard.sh results_doe_scholl_l9
```

Or double-click `launch_dashboard.command` on macOS.

Standalone HTML pages are also available directly:

```text
{output_dir}/index.html
{output_dir}/html/all_campaigns.html
{output_dir}/html/results_doe_scholl_l9.html
```

Optional environment variables:

```bash
HOST=0.0.0.0 PORT=8050 PYTHON_BIN=python3 ./launch_dashboard.sh results_doe_otto_l9
```

## Notes

- `dashboard.py` is copied from the current repo version.
- The result folders come from:
  `{source_bundle}`
- Each campaign directory is already in the new dashboard/result format.
- The dashboard serves one campaign at a time. Pick the campaign name as the
  first argument of `launch_dashboard.sh`.
- The `html/` directory contains static standalone snapshots with embedded data.
- `html/all_campaigns.html` groups all archive campaigns in one page with a
  campaign selector in the header.
"""
    write_text(output_dir / "README.md", text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a standalone archive dashboard bundle."
    )
    parser.add_argument(
        "--source-bundle",
        default=str(PROJECT_ROOT / "published_results" / "archive_v1_newformat_2026-05-13"),
        help="Upgraded archive export bundle to package.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Optional explicit output directory.",
    )
    args = parser.parse_args()

    source_bundle = Path(args.source_bundle).expanduser().resolve()
    if not source_bundle.exists():
        raise SystemExit(f"Source bundle not found: {source_bundle}")

    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser().resolve()
    else:
        stamp = datetime.now().strftime("%Y-%m-%d")
        output_dir = (
            PROJECT_ROOT
            / "published_results"
            / f"archive_v1_dashboard_standalone_{stamp}"
        )

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    campaigns = sorted(
        p.name for p in source_bundle.iterdir() if p.is_dir() and p.name.startswith("results_")
    )
    if not campaigns:
        raise SystemExit(f"No `results_*` campaigns found in {source_bundle}")

    shutil.copy2(PROJECT_ROOT / "scripts" / "dashboard.py", output_dir / "dashboard.py")
    dashboard_template = load_dashboard_template()

    results_root = output_dir / "results"
    results_root.mkdir(parents=True, exist_ok=True)
    html_root = output_dir / "html"
    html_root.mkdir(parents=True, exist_ok=True)
    payloads_by_campaign: dict[str, dict] = {}
    for campaign in campaigns:
        shutil.copytree(source_bundle / campaign, results_root / campaign)
        payload = json.loads(
            (source_bundle / campaign / "dashboard_data.json").read_text(encoding="utf-8")
        )
        payloads_by_campaign[campaign] = payload
        html = build_static_dashboard_html(
            dashboard_template,
            payload,
            f"Archive Dashboard — {campaign}",
        )
        write_text(html_root / f"{campaign}.html", html)

    all_html = build_multi_dashboard_html(
        dashboard_template,
        payloads_by_campaign,
        "Archive Dashboard — All Campaigns",
    )
    write_text(html_root / "all_campaigns.html", all_html)

    for extra_name in ("README.md", "all_run_info_flat.csv"):
        extra_path = source_bundle / extra_name
        if extra_path.exists():
            shutil.copy2(extra_path, output_dir / extra_name)

    build_launcher(output_dir)
    build_index_html(output_dir, campaigns)
    build_readme(output_dir, source_bundle, campaigns)
    print(f"[archive-standalone] bundle ready: {output_dir}")


if __name__ == "__main__":
    main()
