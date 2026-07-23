"""Tests for CLI argument parsing and main entry point."""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os


def test_build_parser_exists():
    """Test that build_parser function exists."""
    import gpm_download
    assert hasattr(gpm_download, "build_parser")


def test_build_parser_returns_parser():
    """Test that build_parser returns an ArgumentParser."""
    import gpm_download
    parser = gpm_download.build_parser()
    assert parser is not None
    # Check it has parse_args method
    assert hasattr(parser, "parse_args")


def test_parser_start_date_required():
    """Test that start-date is required when using main."""
    import gpm_download
    # Without start-date and end-date, should return 2
    with patch("sys.stderr"):
        rc = gpm_download.main(["--end-date", "2024-01-31"])
    assert rc == 2


def test_parser_end_date_required():
    """Test that end-date is required when using main."""
    import gpm_download
    with patch("sys.stderr"):
        rc = gpm_download.main(["--start-date", "2024-01-01"])
    assert rc == 2


def test_parser_list_variables(capsys):
    """Test --list-variables flag."""
    import gpm_download
    rc = gpm_download.main(["--list-variables"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "precipitation" in captured.out
    assert "precipitationCal" in captured.out
    assert "randomError" in captured.out


def test_parser_default_variables():
    """Test default variable is precipitation."""
    import gpm_download
    parser = gpm_download.build_parser()
    args = parser.parse_args(["--start-date", "2024-01-01", "--end-date", "2024-01-31"])
    assert args.variables == ["precipitation"]


def test_parser_custom_variables():
    """Test custom variables parsing."""
    import gpm_download
    parser = gpm_download.build_parser()
    args = parser.parse_args([
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-31",
        "--variables", "precipitation", "precipitationCal",
    ])
    assert args.variables == ["precipitation", "precipitationCal"]


def test_parser_bbox():
    """Test bbox parsing."""
    import gpm_download
    parser = gpm_download.build_parser()
    args = parser.parse_args([
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-31",
        "--bbox", "116.0", "39.0", "117.0", "40.0",
    ])
    assert args.bbox == [116.0, 39.0, 117.0, 40.0]


def test_parser_output_format_default():
    """Test default output format is text."""
    import gpm_download
    parser = gpm_download.build_parser()
    args = parser.parse_args(["--start-date", "2024-01-01", "--end-date", "2024-01-31"])
    assert args.output_format == "text"


def test_parser_output_format_json():
    """Test json output format."""
    import gpm_download
    parser = gpm_download.build_parser()
    args = parser.parse_args([
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-31",
        "--output-format", "json",
    ])
    assert args.output_format == "json"


def test_parser_download_flag():
    """Test --download flag."""
    import gpm_download
    parser = gpm_download.build_parser()
    args = parser.parse_args([
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-31",
        "--download",
    ])
    assert args.download is True


def test_parser_no_progress():
    """Test --no-progress flag."""
    import gpm_download
    parser = gpm_download.build_parser()
    args = parser.parse_args([
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-31",
        "--no-progress",
    ])
    assert args.no_progress is True


def test_parser_quiet():
    """Test --quiet flag."""
    import gpm_download
    parser = gpm_download.build_parser()
    args = parser.parse_args([
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-31",
        "--quiet",
    ])
    assert args.quiet is True


def test_parser_output_dir():
    """Test --output-dir argument."""
    import gpm_download
    parser = gpm_download.build_parser()
    args = parser.parse_args([
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-31",
        "--output-dir", "/tmp/test",
    ])
    assert args.output_dir == "/tmp/test"


def test_parser_offline():
    """Test --offline flag."""
    import gpm_download
    parser = gpm_download.build_parser()
    args = parser.parse_args([
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-31",
        "--offline",
    ])
    assert args.offline is True


def test_main_offline_json(capsys):
    """Test main with offline mode and JSON output."""
    import gpm_download
    rc = gpm_download.main([
        "--start-date", "2024-01-01",
        "--end-date", "2024-01-03",
        "--offline",
        "--output-format", "json",
        "--quiet",
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert '"count": 3' in captured.out


def test_main_invalid_variable():
    """Test main with invalid variable returns error."""
    import gpm_download
    with patch("sys.stderr"):
        rc = gpm_download.main([
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-31",
            "--variables", "invalid_var",
        ])
    assert rc == 2
