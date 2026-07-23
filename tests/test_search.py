"""Tests for search and URL construction functions."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


def test_build_file_url_basic():
    """Test basic URL construction."""
    import gpm_download
    url = gpm_download.build_file_url("2024-01-15", "precipitationCal")
    assert "2024" in url
    assert "01" in url
    assert "3B-DAY-L.MS.MRG.3IMERG.20240115" in url
    assert url.endswith(".HDF5")
    assert "GPM_3IMERGDL.07" in url


def test_build_file_url_different_dates():
    """Test URL construction with different dates."""
    import gpm_download
    url1 = gpm_download.build_file_url("2024-01-01", "precipitationCal")
    url2 = gpm_download.build_file_url("2024-12-31", "precipitationCal")
    assert "20240101" in url1
    assert "20241231" in url2


def test_build_file_url_different_variables():
    """Test URL construction with different variables."""
    import gpm_download
    for var in ["precipitation", "precipitationCal", "randomError"]:
        url = gpm_download.build_file_url("2024-06-15", var)
        assert url.endswith(".HDF5")
        assert "GPM_3IMERGDL.07" in url


def test_build_file_url_invalid_variable():
    """Test URL construction with invalid variable raises error."""
    import gpm_download
    with pytest.raises(ValueError, match="Unknown variable"):
        gpm_download.build_file_url("2024-01-01", "invalid_var")


def test_build_file_url_invalid_date():
    """Test URL construction with invalid date raises error."""
    import gpm_download
    with pytest.raises(ValueError, match="Invalid date format"):
        gpm_download.build_file_url("not-a-date", "precipitation")


def test_build_filename_basic():
    """Test filename construction."""
    import gpm_download
    fname = gpm_download.build_filename("2024-01-15", "precipitationCal")
    assert fname == "gpm_3IMERGDL_20240115_precipitationCal.HDF5"


def test_build_filename_different_dates():
    """Test filename construction with different dates."""
    import gpm_download
    fname1 = gpm_download.build_filename("2024-01-01", "precipitation")
    fname2 = gpm_download.build_filename("2024-12-31", "precipitation")
    assert "20240101" in fname1
    assert "20241231" in fname2


def test_build_filename_different_variables():
    """Test filename construction with different variables."""
    import gpm_download
    for var in ["precipitation", "precipitationCal", "randomError"]:
        fname = gpm_download.build_filename("2024-06-15", var)
        assert var in fname
        assert fname.endswith(".HDF5")


def test_enumerate_dates_single_day():
    """Test date enumeration for single day."""
    import gpm_download
    dates = gpm_download.enumerate_dates("2024-01-01", "2024-01-01")
    assert dates == ["2024-01-01"]


def test_enumerate_dates_range():
    """Test date enumeration for a range."""
    import gpm_download
    dates = gpm_download.enumerate_dates("2024-01-01", "2024-01-05")
    assert len(dates) == 5
    assert dates[0] == "2024-01-01"
    assert dates[-1] == "2024-01-05"


def test_enumerate_dates_month():
    """Test date enumeration for a full month."""
    import gpm_download
    dates = gpm_download.enumerate_dates("2024-01-01", "2024-01-31")
    assert len(dates) == 31


def test_enumerate_dates_invalid_format():
    """Test date enumeration with invalid format."""
    import gpm_download
    with pytest.raises(ValueError, match="Invalid date format"):
        gpm_download.enumerate_dates("2024/01/01", "2024-01-31")


def test_enumerate_dates_reversed():
    """Test date enumeration with reversed dates raises error."""
    import gpm_download
    with pytest.raises(ValueError, match="start_date.*must be <="):
        gpm_download.enumerate_dates("2024-01-31", "2024-01-01")


def test_parse_bbox_valid():
    """Test valid bbox parsing."""
    import gpm_download
    bbox = gpm_download.parse_bbox(["116.0", "39.0", "117.0", "40.0"])
    assert bbox == (116.0, 39.0, 117.0, 40.0)


def test_parse_bbox_none():
    """Test bbox parsing with None returns None."""
    import gpm_download
    assert gpm_download.parse_bbox(None) is None


def test_parse_bbox_empty():
    """Test bbox parsing with empty list returns None."""
    import gpm_download
    assert gpm_download.parse_bbox([]) is None


def test_parse_bbox_wrong_count():
    """Test bbox parsing with wrong count raises error."""
    import gpm_download
    with pytest.raises(ValueError, match="exactly 4 values"):
        gpm_download.parse_bbox(["116.0", "39.0", "117.0"])


def test_parse_bbox_invalid_longitude():
    """Test bbox parsing with invalid longitude raises error."""
    import gpm_download
    with pytest.raises(ValueError, match="longitude"):
        gpm_download.parse_bbox(["200.0", "39.0", "117.0", "40.0"])


def test_parse_bbox_invalid_latitude():
    """Test bbox parsing with invalid latitude raises error."""
    import gpm_download
    with pytest.raises(ValueError, match="latitude"):
        gpm_download.parse_bbox(["116.0", "100.0", "117.0", "40.0"])


def test_parse_bbox_reversed_lon():
    """Test bbox parsing with reversed longitude raises error."""
    import gpm_download
    with pytest.raises(ValueError, match="min_lon must be < max_lon"):
        gpm_download.parse_bbox(["117.0", "39.0", "116.0", "40.0"])


def test_parse_bbox_reversed_lat():
    """Test bbox parsing with reversed latitude raises error."""
    import gpm_download
    with pytest.raises(ValueError, match="min_lat must be < max_lat"):
        gpm_download.parse_bbox(["116.0", "40.0", "117.0", "39.0"])


def test_search_files_offline():
    """Test offline file search."""
    import gpm_download
    files = gpm_download.search_files_offline("2024-01-01", "2024-01-05")
    assert len(files) == 5
    for f in files:
        assert f["exists"] is True
        assert "url" in f
        assert "date" in f
        assert f["variable"] == "precipitation"


def test_search_files_offline_multiple_variables():
    """Test offline file search with multiple variables."""
    import gpm_download
    files = gpm_download.search_files_offline(
        "2024-01-01", "2024-01-03",
        variables=["precipitation", "precipitationCal"],
    )
    assert len(files) == 6  # 3 days * 2 variables


def test_search_files_offline_invalid_variable():
    """Test offline file search with invalid variable."""
    import gpm_download
    with pytest.raises(ValueError, match="Unknown variable"):
        gpm_download.search_files_offline(
            "2024-01-01", "2024-01-31",
            variables=["invalid"],
        )


@patch("requests.Session")
def test_search_files_online(MockSession):
    """Test online file search with mocked requests."""
    import gpm_download

    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_session = MagicMock()
    mock_session.head.return_value = mock_response
    MockSession.return_value = mock_session

    files = gpm_download.search_files(
        "2024-01-01", "2024-01-03",
        timeout=10,
    )
    assert len(files) == 3
    for f in files:
        assert f["exists"] is True


@patch("requests.Session")
def test_search_files_online_not_found(MockSession):
    """Test online file search when files don't exist."""
    import gpm_download

    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_session = MagicMock()
    mock_session.head.return_value = mock_response
    MockSession.return_value = mock_session

    files = gpm_download.search_files(
        "2024-01-01", "2024-01-03",
        timeout=10,
    )
    assert len(files) == 3
    for f in files:
        assert f["exists"] is False


def test_format_results_text():
    """Test text output formatting."""
    import gpm_download
    query_meta = {
        "start_date": "2024-01-01",
        "end_date": "2024-01-03",
        "variables": ["precipitation"],
        "bbox": None,
    }
    files = [
        {"date": "2024-01-01", "variable": "precipitation", "exists": True},
        {"date": "2024-01-02", "variable": "precipitation", "exists": False},
    ]
    text = gpm_download.format_results_text(query_meta, files)
    assert "found 2 file(s)" in text
    assert "Available files" in text
    assert "Unavailable files" in text


def test_format_results_json():
    """Test JSON output formatting."""
    import gpm_download
    import json
    query_meta = {
        "start_date": "2024-01-01",
        "end_date": "2024-01-03",
        "variables": ["precipitation"],
        "bbox": None,
    }
    files = [
        {"date": "2024-01-01", "variable": "precipitation", "exists": True},
    ]
    result = gpm_download.format_results_json(query_meta, files)
    data = json.loads(result)
    assert data["count"] == 1
    assert data["available"] == 1


def test_human_bytes():
    """Test human-readable bytes formatting."""
    import gpm_download
    assert gpm_download._human_bytes(0) == "0 B"
    assert gpm_download._human_bytes(1023) == "1023 B"
    assert "KB" in gpm_download._human_bytes(1024)
    assert "MB" in gpm_download._human_bytes(1024 * 1024)
    assert "GB" in gpm_download._human_bytes(1024 * 1024 * 1024)


def test_render_progress():
    """Test progress bar rendering."""
    import gpm_download
    line = gpm_download._render_progress(50, 100, 10.0, 5.0)
    assert "%" in line
    assert "ETA" in line
    assert "┃" in line


def test_render_progress_unknown_total():
    """Test progress bar with unknown total."""
    import gpm_download
    line = gpm_download._render_progress(50, None, 10.0, None)
    assert "?" in line
