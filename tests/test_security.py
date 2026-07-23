"""Tests for security and safety features."""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock


def test_no_hardcoded_credentials():
    """Verify no hardcoded credentials in the module."""
    import gpm_download
    source = open(gpm_download.__file__).read() if hasattr(gpm_download, '__file__') else ""

    # Check no API keys
    assert "api_key" not in source.lower() or "no API keys" in source.lower()
    assert "secret" not in source.lower() or "no secret" in source.lower()


def test_no_proxy_7897():
    """Verify no references to port 7897."""
    import gpm_download
    # Read the source file
    source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gpm-download.py")
    with open(source_path, "r", encoding="utf-8") as f:
        source = f.read()

    assert "7897" not in source, "Found reference to port 7897"


def test_default_trust_env_false():
    """Test that trust_env defaults to False (no system proxy)."""
    import gpm_download
    assert gpm_download.DEFAULT_TRUST_ENV is False


def test_user_agent_set():
    """Test that User-Agent is set."""
    import gpm_download
    assert "gpm-download" in gpm_download.USER_AGENT
    assert "0.1.0" in gpm_download.USER_AGENT


def test_privacy_notice_function():
    """Test privacy notice function exists."""
    import gpm_download
    assert hasattr(gpm_download, "_emit_privacy_notice")


def test_quiet_env_var(monkeypatch):
    """Test GPM_DOWNLOAD_QUIET env var."""
    import gpm_download
    monkeypatch.delenv("GPM_DOWNLOAD_QUIET", raising=False)
    # Default should be False
    assert gpm_download._quiet() is False


def test_quiet_env_var_set(monkeypatch):
    """Test GPM_DOWNLOAD_QUIET env var when set."""
    import gpm_download
    monkeypatch.setenv("GPM_DOWNLOAD_QUIET", "1")
    assert gpm_download._quiet() is True


def test_download_safe_write():
    """Test that download uses .part temp file for safe writes."""
    import gpm_download

    with tempfile.NamedTemporaryFile(delete=False, suffix=".HDF5") as f:
        dest = f.name

    # Read source to verify .part pattern
    source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gpm-download.py")
    with open(source_path, "r", encoding="utf-8") as f:
        source = f.read()

    assert ".part" in source
    assert "os.replace" in source

    os.unlink(dest)


def test_download_cleanup_on_failure():
    """Test that .part files are cleaned up on failure."""
    import gpm_download

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "test.HDF5")
        part = dest + ".part"

        # Create a .part file
        with open(part, "wb") as f:
            f.write(b"partial data")

        # Mock download to fail after partial write
        with patch("requests.get", side_effect=Exception("fail")):
            ok, msg = gpm_download.download_file(
                "https://example.com/test",
                dest,
                show_progress=False,
            )

        assert ok is False
        assert not os.path.exists(part)


def test_mit0_license():
    """Test LICENSE file exists and is MIT-0."""
    license_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "LICENSE")
    assert os.path.exists(license_path)
    with open(license_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "MIT Zero License" in content or "MIT-0" in content


def test_public_domain_notice():
    """Test that public domain notice is in docstring."""
    import gpm_download
    assert "public domain" in gpm_download.__doc__.lower()


def test_data_source_nasa():
    """Test that data source is NASA GES DISC."""
    import gpm_download
    assert "GES DISC" in gpm_download.__doc__ or "GES DISC" in str(gpm_download.GES_DISC_BASE)


def test_no_authentication_bypass():
    """Verify script doesn't attempt authentication bypass."""
    source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gpm-download.py")
    with open(source_path, "r", encoding="utf-8") as f:
        source = f.read()

    # Should not have password patterns
    assert "password" not in source.lower()
    # Verify docstring states no authentication required
    assert "no authentication" in source.lower() or "no login" in source.lower()
    # Verify it mentions no credentials sent (privacy disclosure is OK)
    assert "no api keys" in source.lower()


def test_url_https():
    """Test that all URLs use HTTPS."""
    import gpm_download
    assert gpm_download.GES_DISC_BASE.startswith("https://")
    assert gpm_download.GPM_3IMERGDL_BASE.startswith("https://")


def test_file_extension_validation():
    """Test that downloaded files use expected extensions."""
    import gpm_download
    fname = gpm_download.build_filename("2024-01-01", "precipitation")
    assert fname.endswith(".HDF5")


def test_no_path_traversal():
    """Test that filenames don't contain path traversal."""
    import gpm_download
    fname = gpm_download.build_filename("2024-01-01", "precipitation")
    assert ".." not in fname
    assert "/" not in fname
    assert "\\" not in fname
