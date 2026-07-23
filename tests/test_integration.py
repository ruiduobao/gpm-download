"""Integration tests for gpm-download (end-to-end CLI flows).

These tests exercise the full CLI pipeline using mocked network calls.
"""

import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock


def test_full_search_flow_json(capsys):
    """Test complete search flow with JSON output."""
    import gpm_download

    rc = gpm_download.main([
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-05",
        "--offline",
        "--output-format", "json",
        "--quiet",
    ])
    assert rc == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["count"] == 5
    assert data["available"] == 5


def test_full_search_flow_text(capsys):
    """Test complete search flow with text output."""
    import gpm_download

    rc = gpm_download.main([
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-05",
        "--offline",
        "--output-format", "text",
        "--quiet",
    ])
    assert rc == 0

    captured = capsys.readouterr()
    assert "found 5 file(s)" in captured.out


def test_full_search_with_variables(capsys):
    """Test search with multiple variables."""
    import gpm_download

    rc = gpm_download.main([
        "--start-date", "2024-06-01",
        "--end-date", "2024-06-03",
        "--variables", "precipitation", "precipitationCal", "randomError",
        "--offline",
        "--output-format", "json",
        "--quiet",
    ])
    assert rc == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["count"] == 9  # 3 days * 3 variables


def test_full_search_with_bbox(capsys):
    """Test search with bounding box."""
    import gpm_download

    rc = gpm_download.main([
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-03",
        "--bbox", "116.0", "39.0", "117.0", "40.0",
        "--offline",
        "--output-format", "json",
        "--quiet",
    ])
    assert rc == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["query"]["bbox"] == [116.0, 39.0, 117.0, 40.0]


@patch("gpm_download.download_file")
def test_full_download_flow(mock_download, capsys):
    """Test complete download flow."""
    import gpm_download

    mock_download.return_value = (True, "ok")

    with tempfile.TemporaryDirectory() as tmpdir:
        rc = gpm_download.main([
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-03",
            "--offline",
            "--download",
            "--output-dir", tmpdir,
            "--quiet",
        ])
        assert rc == 0
        assert mock_download.call_count == 3


@patch("gpm_download.download_file")
def test_full_download_with_variables(mock_download, capsys):
    """Test download with multiple variables."""
    import gpm_download

    mock_download.return_value = (True, "ok")

    with tempfile.TemporaryDirectory() as tmpdir:
        rc = gpm_download.main([
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-03",
            "--variables", "precipitation", "precipitationCal",
            "--offline",
            "--download",
            "--output-dir", tmpdir,
            "--quiet",
        ])
        assert rc == 0
        assert mock_download.call_count == 6  # 3 days * 2 variables


@patch("gpm_download.download_file")
def test_full_download_partial_failure(mock_download, capsys):
    """Test download with partial failures."""
    import gpm_download

    mock_download.side_effect = [
        (True, "ok"),
        (False, "network error"),
        (True, "ok"),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        rc = gpm_download.main([
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-03",
            "--offline",
            "--download",
            "--output-dir", tmpdir,
            "--quiet",
        ])
        assert rc == 1  # Should return 1 due to failure


def test_search_only_no_download(capsys):
    """Test that search-only mode doesn't trigger download."""
    import gpm_download

    with patch("gpm_download.download_files") as mock_dl:
        rc = gpm_download.main([
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-03",
            "--offline",
            "--quiet",
        ])
        assert rc == 0
        mock_dl.assert_not_called()


def test_list_variables_flow(capsys):
    """Test --list-variables flow."""
    import gpm_download

    rc = gpm_download.main(["--list-variables"])
    assert rc == 0

    captured = capsys.readouterr()
    assert "precipitation" in captured.out
    assert "precipitationCal" in captured.out
    assert "randomError" in captured.out
    assert "mm/hr" in captured.out


def test_error_handling_invalid_dates(capsys):
    """Test error handling for invalid dates."""
    import gpm_download

    with patch("sys.stderr"):
        rc = gpm_download.main([
            "--start-date", "invalid",
            "--end-date", "2024-01-31",
            "--offline",
        ])
    assert rc == 2


def test_error_handling_reversed_dates(capsys):
    """Test error handling for reversed date range."""
    import gpm_download

    with patch("sys.stderr"):
        rc = gpm_download.main([
            "--start-date", "2024-12-31",
            "--end-date", "2024-01-01",
            "--offline",
        ])
    assert rc == 2


def test_error_handling_invalid_bbox(capsys):
    """Test error handling for invalid bbox."""
    import gpm_download

    with patch("sys.stderr"):
        rc = gpm_download.main([
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-31",
            "--bbox", "200.0", "39.0", "117.0", "40.0",
            "--offline",
        ])
    assert rc == 2


@patch("requests.Session")
def test_online_search_flow(MockSession, capsys):
    """Test online search with mocked network."""
    import gpm_download

    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_session = MagicMock()
    mock_session.head.return_value = mock_response
    MockSession.return_value = mock_session

    rc = gpm_download.main([
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-03",
        "--output-format", "json",
        "--quiet",
    ])
    assert rc == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["count"] == 3
    assert data["available"] == 3


def test_quiet_suppresses_stderr(capsys):
    """Test that --quiet suppresses stderr output."""
    import gpm_download

    rc = gpm_download.main([
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-03",
        "--offline",
        "--quiet",
        "--output-format", "json",
    ])
    assert rc == 0

    captured = capsys.readouterr()
    # stderr should be empty in quiet mode
    assert captured.err == ""
