---
name: gpm-download
description: 'Download GPM IMERG (Global Precipitation Measurement) precipitation description: 'Download GPM IMERG (Global Precipitation Measurement) precipitation data  from NASA GES DISC. Provides 0.1° resolution global precipitation estimates.  No authentication required.  '
---

# GPM Precipitation Downloader

Download GPM IMERG (Global Precipitation Measurement) precipitation data from NASA GES DISC.

## Overview

This skill downloads GPM IMERG Late Run (GPM_3IMERGDL) daily precipitation data at 0.1° resolution from NASA's Goddard Earth Sciences Data and Information Services Center (GES DISC). Data is freely available via direct HTTPS download.

## Data Source

- **Dataset**: GPM_3IMERGDL (IMERG Late Run Daily)
- **Provider**: NASA GES DISC (disc.gsfc.nasa.gov)
- **Resolution**: 0.1° × 0.1° (~10 km)
- **Variables**: precipitation, precipitationCal, randomError
- **Format**: HDF5 (.HDF5)
- **URL Pattern**: `https://gpmweb2.gesdisc.eosdis.nasa.gov/data/GPM_L3/GPM_3IMERGDL.07/YYYY/MM/`

## Usage

### Search for available files

```bash
python gpm-download.py \
    --start-date 2024-01-01 \
    --end-date 2024-01-31 \
    --bbox 116.0 39.0 117.0 40.0
```

### Download data

```bash
python gpm-download.py \
    --start-date 2024-01-01 \
    --end-date 2024-01-31 \
    --bbox 116.0 39.0 117.0 40.0 \
    --download \
    --output-dir ./gpm_data
```

### Select variables

```bash
python gpm-download.py \
    --start-date 2024-01-01 \
    --end-date 2024-01-31 \
    --variables precipitation precipitationCal \
    --download
```

### JSON output

```bash
python gpm-download.py \
    --start-date 2024-01-01 \
    --end-date 2024-01-31 \
    --output-format json
```

## CLI Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--start-date` | Start date (YYYY-MM-DD) | Required |
| `--end-date` | End date (YYYY-MM-DD) | Required |
| `--bbox` | Bounding box (minLon minLat maxLon maxLat) | Global |
| `--variables` | Variables to download | precipitation |
| `--download` | Trigger download | False (search only) |
| `--output-dir` | Download directory | ./gpm_data |
| `--output-format` | Output format (text/json) | text |
| `--no-progress` | Disable progress bar | False |
| `--quiet` | Suppress progress output | False |
| `--list-variables` | List available variables | - |

## Privacy Disclosure

When this script runs, it sends:
- Date range queries to NASA GES DISC HTTPS endpoints
- No API keys, local files, or PII are sent

## License

MIT-0. GPM data © NASA (public domain).
