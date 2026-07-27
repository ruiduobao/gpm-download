#!/usr/bin/env python3
"""GPM Precipitation Downloader | GPM 降水数据下载器

Download GPM IMERG Late Run (GPM_3IMERGDL) daily precipitation data from
NASA GES DISC. Provides 0.1° resolution global precipitation estimates.

Uses direct HTTPS access to GES DISC archives (no authentication required).
Adopts the same single-file CLI architecture as landsat-download.py with
`.part` safe writes and visual progress bar.

Data Source
-----------
* **NASA GES DISC** (disc.gsfc.nasa.gov) — public HTTPS access
* GPM_3IMERGDL.07 — Late Run Daily precipitation at 0.1° resolution
* URL pattern: ``https://gpmweb2.gesdisc.eosdis.nasa.gov/data/GPM_L3/GPM_3IMERGDL.07/YYYY/MM/``

Privacy disclosure
------------------
When this script runs, it sends:
* Date range queries to NASA GES DISC HTTPS endpoints.
  No API keys, no local files, no PII are sent.

What is NOT sent: any data from the local filesystem, any environment
variables, any login credentials.

To suppress the one-line privacy notice: set ``GPM_DOWNLOAD_QUIET=1``.

Public domain notice
--------------------
GPM IMERG data is provided by NASA and is in the **public domain**.
This skill does not bypass any authentication, login, or access control.

Usage
-----
::

    python gpm-download.py \\
        --start-date 2024-01-01 \\
        --end-date 2024-01-31

    # Search + download
    python gpm-download.py \\
        --start-date 2024-01-01 \\
        --end-date 2024-01-31 \\
        --variables precipitation precipitationCal \\
        --download \\
        --output-dir ./gpm_data

License
-------
MIT-0. GPM data © NASA (public domain).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

# Local helper: --place resolution (vendored copy of _place_resolver.py)
try:
    from _place import resolve_place as _resolve_place
except ImportError:  # pragma: no cover - allow running without helper
    def _resolve_place(*_a, **_kw):  # type: ignore
        raise RuntimeError(
            "place resolution helper (_place.py) not available in this folder"
        )


# ---------------------------------------------------------------------------
# GES DISC endpoints
# ---------------------------------------------------------------------------

GES_DISC_BASE = "https://gpmweb2.gesdisc.eosdis.nasa.gov/data/GPM_L3"
GPM_3IMERGDL_VERSION = "07"
GPM_3IMERGDL_BASE = f"{GES_DISC_BASE}/GPM_3IMERGDL.{GPM_3IMERGDL_VERSION}"

# Available variables in GPM_3IMERGDL
AVAILABLE_VARIABLES = {
    "precipitation": {
        "description": "Surface precipitation (mm/hr)",
        "description_zh": "地表降水 (mm/hr)",
        "hdf5_path": "/Grid/precipitation",
    },
    "precipitationCal": {
        "description": "Calibrated precipitation (mm/hr)",
        "description_zh": "校准降水 (mm/hr)",
        "hdf5_path": "/Grid/precipitationCal",
    },
    "randomError": {
        "description": "Random error estimate (mm/hr)",
        "description_zh": "随机误差估计 (mm/hr)",
        "hdf5_path": "/Grid/randomError",
    },
}

DEFAULT_VARIABLES = ["precipitation"]

USER_AGENT = "gpm-download/0.1.0 (+https://clawhub.ai/skills/gpm-download)"

# Trust env for proxies: default False (direct connection)
DEFAULT_TRUST_ENV = os.environ.get("GPM_DOWNLOAD_USE_PROXY") == "1"


# ---------------------------------------------------------------------------
# Privacy notice helper
# ---------------------------------------------------------------------------

def _quiet() -> bool:
    return os.environ.get("GPM_DOWNLOAD_QUIET") == "1"


def _emit_privacy_notice() -> None:
    """One-line stderr note about what the script is doing on the network."""
    if _quiet():
        return
    msg = (
        "[gpm-download] contacting NASA GES DISC endpoint "
        "(no API keys / no local files / no PII sent; "
        "GPM data © NASA public domain). "
        "Set GPM_DOWNLOAD_QUIET=1 to suppress this notice."
    )
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------

def build_file_url(date_str: str, variable: str = "precipitationCal") -> str:
    """Build the direct HTTPS URL for a GPM_3IMERGDL daily file.

    Parameters
    ----------
    date_str : str
        Date in ``YYYY-MM-DD`` format.
    variable : str
        Variable name (used for filename construction).

    Returns
    -------
    str
        Full HTTPS URL to the HDF5 file on GES DISC.

    Raises
    ------
    ValueError
        If date_str is not valid or variable is not supported.
    """
    if variable not in AVAILABLE_VARIABLES:
        raise ValueError(f"Unknown variable: {variable!r}; expected one of {list(AVAILABLE_VARIABLES)}")

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str!r}; expected YYYY-MM-DD")

    year = dt.strftime("%Y")
    month = dt.strftime("%m")
    day = dt.strftime("%d")
    doy = dt.strftime("%j")

    # GPM_3IMERGDL filename pattern:
    # 3B-DAY-L.MS.MRG.3IMERG.YYYYMMDD-S000000-E235959.V07A.HDF5
    # but actual files use: 3B-DAY-L.MS.MRG.3IMERG.YYYYMMDD-S000000-E235959.V07B.HDF5
    filename = f"3B-DAY-L.MS.MRG.3IMERG.{year}{month}{day}-S000000-E235959.V07B.HDF5"

    url = f"{GPM_3IMERGDL_BASE}/{year}/{month}/{filename}"
    return url


def build_filename(date_str: str, variable: str = "precipitationCal") -> str:
    """Build the local filename for a GPM download.

    Parameters
    ----------
    date_str : str
        Date in ``YYYY-MM-DD`` format.
    variable : str
        Variable name.

    Returns
    -------
    str
        Filename like ``gpm_3IMERGDL_20240101_precipitationCal.HDF5``.
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str!r}; expected YYYY-MM-DD")

    return f"gpm_3IMERGDL_{dt.strftime('%Y%m%d')}_{variable}.HDF5"


def parse_bbox(bbox_list) -> Optional[Tuple[float, float, float, float]]:
    """Parse and validate a bounding box.

    Parameters
    ----------
    bbox_list : list of str or None
        Bounding box as [west, south, east, north] or None/empty.

    Returns
    -------
    tuple of (float, float, float, float) or None
        (min_lon, min_lat, max_lon, max_lat) or None if input is None/empty.

    Raises
    ------
    ValueError
        If bbox is invalid (wrong count, out of range, reversed).
    """
    if bbox_list is None or len(bbox_list) == 0:
        return None
    if len(bbox_list) != 4:
        raise ValueError(f"bbox must have exactly 4 values (west south east north), got {len(bbox_list)}")

    try:
        west, south, east, north = float(bbox_list[0]), float(bbox_list[1]), float(bbox_list[2]), float(bbox_list[3])
    except (ValueError, TypeError) as e:
        raise ValueError(f"bbox values must be numeric: {e}")

    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise ValueError(f"longitude must be between -180 and 180, got west={west}, east={east}")
    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise ValueError(f"latitude must be between -90 and 90, got south={south}, north={north}")
    if west >= east:
        raise ValueError(f"min_lon must be < max_lon, got west={west}, east={east}")
    if south >= north:
        raise ValueError(f"min_lat must be < max_lat, got south={south}, north={north}")

    return (west, south, east, north)


def enumerate_dates(start_date: str, end_date: str) -> List[str]:
    """Generate a list of date strings between start and end (inclusive).

    Parameters
    ----------
    start_date, end_date : str
        Dates in ``YYYY-MM-DD`` format.

    Returns
    -------
    list of str
        List of date strings in ``YYYY-MM-DD`` format.
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid date format; expected YYYY-MM-DD")

    if start > end:
        raise ValueError(f"start_date ({start_date}) must be <= end_date ({end_date})")

    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates


# ---------------------------------------------------------------------------
# Search (list available files)
# ---------------------------------------------------------------------------

def search_files(
    start_date: str,
    end_date: str,
    variables: Optional[List[str]] = None,
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    """Search for available GPM IMERG files.

    Parameters
    ----------
    start_date, end_date : str
        Date range in ``YYYY-MM-DD`` format.
    variables : list of str, optional
        Variables to search for. Defaults to ``["precipitation"]``.
    timeout : int
        HTTP timeout in seconds.

    Returns
    -------
    list of dict
        Each dict has keys: ``date``, ``variable``, ``url``, ``exists``.
    """
    if variables is None:
        variables = DEFAULT_VARIABLES

    for var in variables:
        if var not in AVAILABLE_VARIABLES:
            raise ValueError(f"Unknown variable: {var!r}; expected one of {list(AVAILABLE_VARIABLES)}")

    dates = enumerate_dates(start_date, end_date)
    results = []

    session = requests.Session()
    session.trust_env = DEFAULT_TRUST_ENV
    session.headers.update({"User-Agent": USER_AGENT})

    for date_str in dates:
        for var in variables:
            url = build_file_url(date_str, var)
            # Check if file exists via HEAD request
            try:
                r = session.head(url, timeout=timeout, allow_redirects=True)
                exists = r.status_code == 200
            except requests.RequestException:
                exists = False

            results.append({
                "date": date_str,
                "variable": var,
                "url": url,
                "exists": exists,
            })

    return results


def search_files_offline(
    start_date: str,
    end_date: str,
    variables: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Generate file URLs without checking existence (offline mode).

    Parameters
    ----------
    start_date, end_date : str
        Date range in ``YYYY-MM-DD`` format.
    variables : list of str, optional
        Variables to search for. Defaults to ``["precipitation"]``.

    Returns
    -------
    list of dict
        Each dict has keys: ``date``, ``variable``, ``url``, ``exists`` (always True).
    """
    if variables is None:
        variables = DEFAULT_VARIABLES

    for var in variables:
        if var not in AVAILABLE_VARIABLES:
            raise ValueError(f"Unknown variable: {var!r}; expected one of {list(AVAILABLE_VARIABLES)}")

    dates = enumerate_dates(start_date, end_date)
    results = []

    for date_str in dates:
        for var in variables:
            url = build_file_url(date_str, var)
            results.append({
                "date": date_str,
                "variable": var,
                "url": url,
                "exists": True,  # Assume exists in offline mode
            })

    return results


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_results_text(
    query_meta: Dict[str, Any],
    files: List[Dict[str, Any]],
) -> str:
    """Format search results as human-readable text."""
    lines = []
    lines.append(f"[gpm-download] found {len(files)} file(s)")
    lines.append(f"[gpm-download] date range: {query_meta['start_date']} → {query_meta['end_date']}")
    lines.append(f"[gpm-download] variables: {', '.join(query_meta.get('variables', ['precipitation']))}")
    lines.append("")

    available = [f for f in files if f.get("exists")]
    unavailable = [f for f in files if not f.get("exists")]

    if available:
        lines.append(f"  Available files ({len(available)}):")
        for f in available:
            lines.append(f"    {f['date']}  {f['variable']:<20s}  ✓")
    if unavailable:
        lines.append(f"\n  Unavailable files ({len(unavailable)}):")
        for f in unavailable:
            lines.append(f"    {f['date']}  {f['variable']:<20s}  ✗")

    if not files:
        lines.append("  (no files match the query — try widening date range)")

    return "\n".join(lines)


def format_results_json(
    query_meta: Dict[str, Any],
    files: List[Dict[str, Any]],
) -> str:
    """Format search results as JSON."""
    return json.dumps(
        {
            "query": query_meta,
            "count": len(files),
            "available": sum(1 for f in files if f.get("exists")),
            "files": files,
        },
        ensure_ascii=False,
        indent=2,
    )


# ---------------------------------------------------------------------------
# Download with progress
# ---------------------------------------------------------------------------

def _human_bytes(n: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _render_progress(
    downloaded: int,
    total: Optional[int],
    speed_bps: float,
    eta_seconds: Optional[float],
    bar_width: int = 30,
) -> str:
    """Render a single-line progress bar."""
    if total and total > 0:
        pct = downloaded / total
        filled = int(bar_width * pct)
        bar = "█" * filled + "░" * (bar_width - filled)
        pct_str = f"{pct * 100:5.1f}%"
    else:
        bar = "?" * bar_width
        pct_str = "  ?  %"

    dl_str = _human_bytes(downloaded)
    tot_str = _human_bytes(total) if total and total > 0 else "??"
    speed_str = f"{_human_bytes(int(speed_bps))}/s"

    if eta_seconds is not None and eta_seconds >= 0:
        m, s = divmod(int(eta_seconds), 60)
        eta_str = f"{m}:{s:02d}"
    else:
        eta_str = "  ?  "

    return f"┃{bar}┃ {pct_str}  {dl_str:>9s} / {tot_str:<9s}  {speed_str:>11s}  ETA {eta_str}"


def download_file(
    url: str,
    dest_path: str,
    timeout: int = 600,
    show_progress: bool = True,
) -> Tuple[bool, str]:
    """Download one file to ``dest_path`` via a ``.part`` temp file.

    Parameters
    ----------
    url : str
        Source URL.
    dest_path : str
        Destination file path.
    timeout : int
        HTTP timeout in seconds.
    show_progress : bool
        Whether to show progress bar.

    Returns
    -------
    tuple of (bool, str)
        ``(ok, message)``. On success the ``.part`` file is renamed
        to the final ``dest_path``. On failure the ``.part`` file is removed.
    """
    tmp_path = dest_path + ".part"

    if os.path.exists(dest_path) and not os.path.exists(tmp_path):
        if not _quiet():
            print(f"  ↳ {os.path.basename(dest_path):<40s} already exists, skipping", file=sys.stderr)
        return True, "already exists, skipping"

    try:
        with requests.get(
            url,
            stream=True,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        ) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length", 0)) or None
            downloaded = 0
            t0 = time.time()
            last_print = t0

            with open(tmp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if show_progress and not _quiet() and (now - last_print) > 0.1:
                        elapsed = now - t0
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        eta = ((total - downloaded) / speed) if (total and speed > 0) else None
                        line = _render_progress(downloaded, total, speed, eta)
                        sys.stdout.write(f"\r  ↳ {os.path.basename(dest_path):<40s} {line}")
                        sys.stdout.flush()
                        last_print = now

        if show_progress and not _quiet():
            sys.stdout.write("\n")
            sys.stdout.flush()
        os.replace(tmp_path, dest_path)
        return True, "ok"
    except Exception as e:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return False, str(e)[:200]


def download_files(
    files: List[Dict[str, Any]],
    output_dir: str,
    timeout: int = 600,
    show_progress: bool = True,
) -> Dict[str, Any]:
    """Download multiple GPM files.

    Parameters
    ----------
    files : list of dict
        Files to download (from search_files).
    output_dir : str
        Output directory.
    timeout : int
        Per-file download timeout.
    show_progress : bool
        Whether to show progress bars.

    Returns
    -------
    dict
        Result with keys: ``ok``, ``files``, ``total_bytes``.
    """
    os.makedirs(output_dir, exist_ok=True)

    result: Dict[str, Any] = {
        "ok": True,
        "files": [],
        "total_bytes": 0,
    }

    available = [f for f in files if f.get("exists")]
    if not available:
        if not _quiet():
            print("[gpm-download] no files available to download.", file=sys.stderr)
        return result

    if not _quiet():
        print(f"\n[gpm-download] downloading {len(available)} file(s) to {output_dir}",
              file=sys.stderr)

    for i, file_info in enumerate(available, 1):
        date_str = file_info["date"]
        var = file_info["variable"]
        url = file_info["url"]
        filename = build_filename(date_str, var)
        dest_path = os.path.join(output_dir, filename)

        if not _quiet():
            print(f"\n[{i}/{len(available)}] {date_str} {var}", file=sys.stderr)

        ok, msg = download_file(url, dest_path, timeout=timeout, show_progress=show_progress)
        result["files"].append({
            "date": date_str,
            "variable": var,
            "path": dest_path,
            "ok": ok,
            "message": msg,
        })

        if ok and os.path.exists(dest_path):
            result["total_bytes"] += os.path.getsize(dest_path)
        if not ok:
            result["ok"] = False

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    p = argparse.ArgumentParser(
        prog="gpm-download",
        description=(
            "Download GPM IMERG Late Run (GPM_3IMERGDL) daily precipitation "
            "data from NASA GES DISC. 0.1° resolution global coverage. "
            "从 NASA GES DISC 下载 GPM IMERG 晚期日降水数据。"
        ),
    )
    p.add_argument(
        "--start-date",
        help="Start date YYYY-MM-DD / 开始日期",
    )
    p.add_argument(
        "--end-date",
        help="End date YYYY-MM-DD / 结束日期",
    )
    p.add_argument(
        "--variables",
        nargs="+",
        default=DEFAULT_VARIABLES,
        help=f"Variables to download (default: {' '.join(DEFAULT_VARIABLES)})",
    )
    p.add_argument(
        "--download",
        action="store_true",
        help="Trigger actual download (default: search only) / 实际下载",
    )
    p.add_argument(
        "--output-dir",
        default="./gpm_data",
        help="Download directory (default ./gpm_data) / 下载目录",
    )
    p.add_argument(
        "--output-format",
        default="text",
        choices=["text", "json"],
        help="Output format / 输出格式",
    )
    p.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable visual progress bar / 关闭进度条",
    )
    p.add_argument(
        "--download-timeout",
        type=int,
        default=600,
        help="Per-file download timeout in seconds (default 600)",
    )
    p.add_argument(
        "--list-variables",
        action="store_true",
        help="List available variables and exit / 列出所有变量",
    )
    p.add_argument(
        "--offline",
        action="store_true",
        help="Skip HEAD checks, assume all files exist / 离线模式",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress + privacy notice (also GPM_DOWNLOAD_QUIET=1)",
    )
    p.add_argument(
        "--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"),
        help="Bounding box filter (west south east north) / 边界框过滤",
    )
    p.add_argument(
        "--place",
        help="Place name (Chinese or English). Auto-resolved to bbox via Open-Meteo + Nominatim. "
             "Mutually exclusive with --bbox / 行政地名 (自动解析为 bbox)",
    )
    p.add_argument(
        "--place-buffer-deg",
        type=float,
        default=0.5,
        help="Buffer (degrees) added around the resolved point when --place is used "
             "(default 0.5; ignored if --bbox also given) / 围绕地名的 bbox 缓冲（度）",
    )
    p.add_argument(
        "--no-nominatim",
        action="store_true",
        help="Skip Nominatim lookup in --place resolution / --place 解析时跳过 Nominatim",
    )
    p.add_argument(
        "--qa",
        metavar="PATH",
        help="Write a JSON QA summary (search results, picked files, totals) "
             "to PATH. Implies --download. / 写出 QA 摘要 JSON",
    )
    p.add_argument(
        "--export-csv",
        metavar="PATH",
        help="After download, compute per-day zonal mean (mm/hr) over the bbox "
             "and write to CSV. Requires h5py/numpy; silently skipped if missing. / "
             "写出 bbox 内日均降水 CSV",
    )
    p.add_argument(
        "--export-summary",
        action="store_true",
        help="Print a one-line summary per downloaded file (variable, byte size).",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point."""
    args = build_parser().parse_args(argv)

    # --list-variables
    if args.list_variables:
        print("Available GPM IMERG variables:")
        print("-" * 60)
        for k, v in AVAILABLE_VARIABLES.items():
            print(f"  {k:<20s}  {v['description']:<30s}  {v['description_zh']}")
        return 0

    # Required args check
    missing = []
    if not args.start_date:
        missing.append("--start-date")
    if not args.end_date:
        missing.append("--end-date")
    if missing:
        print(f"ERROR: missing required arguments: {', '.join(missing)}", file=sys.stderr)
        print(f"Run with --help for usage.", file=sys.stderr)
        return 2

    # --quiet on CLI overrides env
    if args.quiet:
        os.environ["GPM_DOWNLOAD_QUIET"] = "1"

    # Validate variables
    for var in args.variables:
        if var not in AVAILABLE_VARIABLES:
            print(f"ERROR: unknown variable: {var!r}", file=sys.stderr)
            print(f"Available: {', '.join(AVAILABLE_VARIABLES.keys())}", file=sys.stderr)
            return 2

    # Validate bbox if provided
    if args.bbox:
        try:
            parse_bbox(args.bbox)
        except ValueError as e:
            print(f"ERROR: invalid bbox: {e}", file=sys.stderr)
            return 2

    # Resolve --place to bbox if given
    place_info: Optional[Dict[str, Any]] = None
    if args.place:
        if args.bbox:
            print(
                "ERROR: --place and --bbox are mutually exclusive; pick one.",
                file=sys.stderr,
            )
            return 2
        try:
            place_info = _resolve_place(
                args.place,
                allow_nominatim=not args.no_nominatim,
            )
        except Exception as e:
            print(f"ERROR: --place resolution failed: {e}", file=sys.stderr)
            return 2
        # Build a bbox from the place centroid with the requested buffer
        w = place_info["lon"] - args.place_buffer_deg
        e = place_info["lon"] + args.place_buffer_deg
        s = place_info["lat"] - args.place_buffer_deg
        n = place_info["lat"] + args.place_buffer_deg
        args.bbox = [w, s, e, n]
        if not _quiet():
            print(
                f"[gpm-download] place: {place_info.get('display_name') or args.place}",
                file=sys.stderr,
            )
            print(
                f"[gpm-download] resolved to bbox {args.bbox} "
                f"(buffer {args.place_buffer_deg}°)",
                file=sys.stderr,
            )
            print(
                f"[gpm-download] geocoder source: {place_info.get('source')}",
                file=sys.stderr,
            )

    # --qa implies --download
    if args.qa:
        args.download = True

    query_meta = {
        "start_date": args.start_date,
        "end_date": args.end_date,
        "variables": args.variables,
        "bbox": args.bbox,
    }

    if not _quiet():
        if args.offline:
            print(f"[gpm-download] offline mode: using bundled catalog",
                  file=sys.stderr)
        else:
            print(f"[gpm-download] searching GES DISC for GPM_3IMERGDL files ...",
                  file=sys.stderr)
    if not args.offline:
        _emit_privacy_notice()
        if not _quiet():
            print(f"[gpm-download] date:      {args.start_date} → {args.end_date}",
                  file=sys.stderr)
            print(f"[gpm-download] variables: {' '.join(args.variables)}",
                  file=sys.stderr)

    try:
        if args.offline:
            files = search_files_offline(
                start_date=args.start_date,
                end_date=args.end_date,
                variables=args.variables,
            )
        else:
            files = search_files(
                start_date=args.start_date,
                end_date=args.end_date,
                variables=args.variables,
                timeout=args.download_timeout,
            )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except requests.RequestException as e:
        print(f"ERROR: network error during search: {e}", file=sys.stderr)
        return 1

    query_meta["returned"] = len(files)

    # Output search results
    if args.output_format == "json":
        print(format_results_json(query_meta, files))
    else:
        print(format_results_text(query_meta, files))

    # Download?
    if not args.download:
        if not _quiet():
            print("\n[gpm-download] search done. Add --download to fetch.",
                  file=sys.stderr)
        return 0

    # Download loop
    if not files:
        if not _quiet():
            print("[gpm-download] no files to download.", file=sys.stderr)
        return 0

    t0 = time.time()
    result = download_files(
        files,
        output_dir=args.output_dir,
        timeout=args.download_timeout,
        show_progress=not args.no_progress,
    )
    elapsed = time.time() - t0

    if not _quiet():
        print(f"\n[gpm-download] done in {elapsed:.0f}s — "
              f"downloaded {_human_bytes(result['total_bytes'])} across "
              f"{len(result['files'])} file(s)",
              file=sys.stderr)

    # Optional summary printout
    if args.export_summary:
        for f in result.get("files", []):
            sz = os.path.getsize(f["path"]) if os.path.exists(f["path"]) else 0
            print(
                f"  {f['date']}  {f['variable']:<16s}  "
                f"{_human_bytes(sz):>10s}  {f.get('message', '')}",
                file=sys.stderr,
            )

    # Optional CSV export (zonal mean per day)
    if args.export_csv:
        try:
            from _export_csv import export_zonal_csv
            export_zonal_csv(
                files=result.get("files", []),
                bbox=args.bbox,
                output_csv=args.export_csv,
            )
            if not _quiet():
                print(
                    f"[gpm-download] wrote zonal-mean CSV to {args.export_csv}",
                    file=sys.stderr,
                )
        except ImportError:
            print(
                "ERROR: --export-csv requires h5py + numpy. "
                "Install with: pip install h5py numpy",
                file=sys.stderr,
            )
            return 3
        except Exception as e:
            print(f"ERROR: --export-csv failed: {e}", file=sys.stderr)
            return 3

    # Optional QA summary
    if args.qa:
        try:
            qa = {
                "skill": "gpm-download",
                "version": "0.2.0",
                "query": {
                    "start_date": args.start_date,
                    "end_date": args.end_date,
                    "variables": args.variables,
                    "bbox": args.bbox,
                    "place": (
                        {
                            "query": place_info["query"] if place_info else None,
                            "display_name": place_info.get("display_name") if place_info else None,
                            "source": place_info.get("source") if place_info else None,
                            "buffer_deg": args.place_buffer_deg if place_info else None,
                        }
                        if place_info
                        else None
                    ),
                },
                "source": "NASA GES DISC (GPM_3IMERGDL.07)",
                "searched": len(files),
                "downloaded": sum(1 for f in result.get("files", []) if f.get("ok")),
                "failed": sum(1 for f in result.get("files", []) if not f.get("ok")),
                "total_bytes": result.get("total_bytes", 0),
                "elapsed_seconds": round(elapsed, 1),
                "files": [
                    {
                        "date": f["date"],
                        "variable": f["variable"],
                        "path": f["path"],
                        "ok": f.get("ok"),
                        "size_bytes": (
                            os.path.getsize(f["path"]) if os.path.exists(f["path"]) else 0
                        ),
                        "message": f.get("message", ""),
                    }
                    for f in result.get("files", [])
                ],
                "exported_csv": args.export_csv,
            }
            with open(args.qa, "w", encoding="utf-8") as f:
                json.dump(qa, f, ensure_ascii=False, indent=2)
            if not _quiet():
                print(f"[gpm-download] wrote QA summary to {args.qa}", file=sys.stderr)
        except Exception as e:
            print(f"ERROR: --qa write failed: {e}", file=sys.stderr)
            return 3

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
