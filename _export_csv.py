"""Zonal mean CSV export for GPM_3IMERGDL files.

Reads HDF5 files (one per day) and computes the mean precipitation within
the supplied bbox (in WGS84 degrees) for each variable. Writes a tidy
CSV with one row per (date, variable).

Privacy: pure local file reads. No network.
"""
from __future__ import annotations

import csv
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import h5py  # type: ignore
except ImportError:  # pragma: no cover
    h5py = None  # type: ignore


# IMERG HDF5 grid: 0.1° lon/lat, lon=-179.95..179.95, lat=-89.95..89.95
GRID_NLON = 3600
GRID_NLAT = 1800
LON_START = -179.95
LAT_START = -89.95
RESOLUTION = 0.1

HDF5_VARS = {
    "precipitation": "/Grid/precipitation",
    "precipitationCal": "/Grid/precipitationCal",
    "randomError": "/Grid/randomError",
}


def _bbox_to_indices(
    bbox: Optional[List[float]],
) -> Tuple[int, int, int, int]:
    """Convert WGS84 bbox to IMERG row/col slices.

    IMERG grid layout (verified against HDF5 files):
    - shape: (1800, 3600) = (lat, lon)
    - row 0 corresponds to latitude +89.95 (top, north)
    - row 1799 corresponds to latitude -89.95 (bottom, south)
    - col 0 corresponds to longitude -179.95 (left, west)
    - col 3599 corresponds to longitude +179.95 (right, east)
    """
    if bbox is None or len(bbox) != 4:
        return 0, GRID_NLON, 0, GRID_NLAT
    w, s, e, n = bbox
    # col index from west to east: lon = -179.95 + col * 0.1
    col_w = int(max(0, np.floor((w - LON_START) / RESOLUTION)))
    col_e = int(min(GRID_NLON, np.ceil((e - LON_START) / RESOLUTION) + 1))
    # row index: row 0 is north, lat = 89.95 - row * 0.1
    #   → row = (89.95 - lat) / 0.1
    row_n = int(np.floor((89.95 - n) / RESOLUTION))
    row_s = int(np.ceil((89.95 - s) / RESOLUTION) + 1)
    col_w = max(0, min(col_w, GRID_NLON))
    col_e = max(col_w, min(col_e, GRID_NLON))
    row_n = max(0, min(row_n, GRID_NLAT))
    row_s = max(row_n, min(row_s, GRID_NLAT))
    return col_w, col_e, row_n, row_s


def _file_zonal_mean(path: str, bbox: Optional[List[float]]) -> Dict[str, float]:
    """Return ``{variable: mean}`` for a single IMERG HDF5 file."""
    if h5py is None:
        raise RuntimeError("h5py not installed")
    out: Dict[str, float] = {}
    with h5py.File(path, "r") as f:
        col_w, col_e, row_n, row_s = _bbox_to_indices(bbox)
        for var_name, hdf5_path in HDF5_VARS.items():
            if hdf5_path not in f:
                continue
            data = f[hdf5_path][row_n:row_s, col_w:col_e]
            data = np.asarray(data, dtype="float32")
            valid = data[data > -1000]  # IMERG nodata sentinel
            if valid.size == 0:
                out[var_name] = float("nan")
            else:
                out[var_name] = float(np.mean(valid))
    return out


def export_zonal_csv(
    files: List[Dict[str, Any]],
    bbox: Optional[List[float]],
    output_csv: str,
) -> int:
    """Compute zonal means for each file and write to CSV.

    Returns the number of rows written.
    """
    rows: List[Dict[str, Any]] = []
    for f in files:
        path = f.get("path")
        date = f.get("date")
        if not path or not os.path.exists(path):
            continue
        try:
            means = _file_zonal_mean(path, bbox)
        except Exception as e:  # noqa: BLE001
            print(
                f"  WARN: {os.path.basename(path)}: {e}",
                file=sys.stderr,
            )
            continue
        for var, m in means.items():
            rows.append(
                {
                    "date": date,
                    "variable": var,
                    "mean_mm_per_hr": round(m, 4) if m == m else None,
                    "path": path,
                    "bbox": ",".join(f"{x:.4f}" for x in bbox) if bbox else None,
                }
            )

    fieldnames = ["date", "variable", "mean_mm_per_hr", "bbox", "path"]
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)
