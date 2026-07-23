"""Tests for download functionality."""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock


def test_download_file_already_exists():
    """Test that existing files are skipped."""
    import gpm_download

    with tempfile.NamedTemporaryFile(delete=False, suffix=".HDF5") as f:
        f.write(b"test data")
        dest = f.name

    try:
        ok, msg = gpm_download.download_file(
            "https://example.com/test.HDF5",
            dest,
            show_progress=False,
        )
        assert ok is True
        assert "already exists" in msg
    finally:
        os.unlink(dest)


@patch("requests.get")
def test_download_file_success(mock_get):
    """Test successful file download."""
    import gpm_download

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Length": "100"}
    mock_response.iter_content.return_value = [b"x" * 50, b"y" * 50]
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_get.return_value = mock_response

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "test.HDF5")
        ok, msg = gpm_download.download_file(
            "https://example.com/test.HDF5",
            dest,
            show_progress=False,
        )
        assert ok is True
        assert msg == "ok"
        assert os.path.exists(dest)
        assert os.path.getsize(dest) == 100


@patch("requests.get")
def test_download_file_failure(mock_get):
    """Test failed file download."""
    import gpm_download

    mock_get.side_effect = Exception("Network error")

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "test.HDF5")
        ok, msg = gpm_download.download_file(
            "https://example.com/test.HDF5",
            dest,
            show_progress=False,
        )
        assert ok is False
        assert "Network error" in msg
        assert not os.path.exists(dest + ".part")


@patch("requests.get")
def test_download_file_cleans_part_on_failure(mock_get):
    """Test that .part file is cleaned up on failure."""
    import gpm_download

    def side_effect(*args, **kwargs):
        # Simulate partial write then failure
        raise Exception("Connection reset")

    mock_get.side_effect = side_effect

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "test.HDF5")
        ok, msg = gpm_download.download_file(
            "https://example.com/test.HDF5",
            dest,
            show_progress=False,
        )
        assert ok is False
        assert not os.path.exists(dest + ".part")


@patch("requests.get")
def test_download_file_progress(mock_get, capsys):
    """Test download with progress output."""
    import gpm_download

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Length": "1000"}
    mock_response.iter_content.return_value = [b"x" * 500, b"y" * 500]
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_get.return_value = mock_response

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "test.HDF5")
        ok, msg = gpm_download.download_file(
            "https://example.com/test.HDF5",
            dest,
            show_progress=True,
        )
        assert ok is True


@patch("requests.get")
def test_download_file_http_error(mock_get):
    """Test download with HTTP error."""
    import gpm_download
    from requests.exceptions import HTTPError

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = HTTPError("404 Not Found")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_get.return_value = mock_response

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "test.HDF5")
        ok, msg = gpm_download.download_file(
            "https://example.com/test.HDF5",
            dest,
            show_progress=False,
        )
        assert ok is False


def test_download_files_empty():
    """Test download with empty file list."""
    import gpm_download

    with tempfile.TemporaryDirectory() as tmpdir:
        result = gpm_download.download_files([], tmpdir, show_progress=False)
        assert result["ok"] is True
        assert result["total_bytes"] == 0


@patch("gpm_download.download_file")
def test_download_files_multiple(mock_download):
    """Test downloading multiple files."""
    import gpm_download

    mock_download.return_value = (True, "ok")

    files = [
        {"date": "2024-01-01", "variable": "precipitation", "exists": True, "url": "https://example.com/1"},
        {"date": "2024-01-02", "variable": "precipitation", "exists": True, "url": "https://example.com/2"},
        {"date": "2024-01-03", "variable": "precipitation", "exists": False, "url": "https://example.com/3"},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        result = gpm_download.download_files(files, tmpdir, show_progress=False)
        assert result["ok"] is True
        # Only 2 calls because 1 file doesn't exist
        assert mock_download.call_count == 2


@patch("gpm_download.download_file")
def test_download_files_partial_failure(mock_download):
    """Test download with partial failures."""
    import gpm_download

    mock_download.side_effect = [
        (True, "ok"),
        (False, "network error"),
    ]

    files = [
        {"date": "2024-01-01", "variable": "precipitation", "exists": True, "url": "https://example.com/1"},
        {"date": "2024-01-02", "variable": "precipitation", "exists": True, "url": "https://example.com/2"},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        result = gpm_download.download_files(files, tmpdir, show_progress=False)
        assert result["ok"] is False
        assert len(result["files"]) == 2


def test_download_creates_output_dir():
    """Test that output directory is created."""
    import gpm_download

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = os.path.join(tmpdir, "new_dir", "sub_dir")
        result = gpm_download.download_files([], output_dir, show_progress=False)
        assert os.path.exists(output_dir)


@patch("gpm_download.download_file")
def test_download_quiet_mode(mock_download, monkeypatch):
    """Test download in quiet mode."""
    import gpm_download

    monkeypatch.setenv("GPM_DOWNLOAD_QUIET", "1")
    mock_download.return_value = (True, "ok")

    files = [
        {"date": "2024-01-01", "variable": "precipitation", "exists": True, "url": "https://example.com/1"},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        result = gpm_download.download_files(files, tmpdir, show_progress=True)
        assert result["ok"] is True
