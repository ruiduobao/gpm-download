"""Pytest configuration for gpm-download tests.

Loads gpm-download.py as a importable module (gpm_download).
"""

import importlib.util
import os
import sys

# Load gpm-download.py as gpm_download module
_script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_script_path = os.path.join(_script_dir, "gpm-download.py")

if os.path.exists(_script_path):
    spec = importlib.util.spec_from_file_location("gpm_download", _script_path)
    gpm_download = importlib.util.module_from_spec(spec)
    sys.modules["gpm_download"] = gpm_download
    spec.loader.exec_module(gpm_download)
