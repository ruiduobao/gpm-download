# GPM Precipitation Downloader · GPM 降水卫星下载器

> 下载 **GPM IMERG** 全球降水测量数据。
> 数据来源为 NASA GES DISC（公开数据，无需账号）。
> MIT-0 开源。

[English](#quickstart) | 中文

## 为什么做这个

GPM（全球降水测量）是 TRMM 的后续任务，提供全球 0.1° 分辨率的
降水估计（IMERG）。水文、气候、农业研究必备。NASA GES DISC 提供
免费 HTTPS 下载，但手动选择产品和日期范围比较繁琐。本 skill 自动化了整个流程。


## Installation

### Cross-platform (skills.sh · 50+ AI agents)

```bash
npx skills add ruiduobao/gpm-download -g
```

Works with: Claude Code, Cursor, Codex, GitHub Copilot, Windsurf, Gemini CLI, Cline, AMP, VS Code, Zed, OpenClaw, and more.

### Claude Code (plugin marketplace)

```bash
/plugin marketplace add ruiduobao/claude-plugins
/plugin install gpm-download@ruiduobao-geo-skills
```

### ClawHub (OpenClaw)

```bash
clawhub install ruiduobao/gpm-download
```

### Manual

```bash
git clone https://github.com/ruiduobao/gpm-download.git
```

## Quickstart / 快速开始

```bash
# 安装依赖
pip install 'requests>=2.28.0'

# 搜索 GPM 降水数据
python gpm-download.py search \
    --bbox 116.0 39.0 117.0 40.0 \
    --start-date 2024-06-01 \
    --end-date 2024-06-30

# 下载降水数据
python gpm-download.py download \
    --bbox 116.0 39.0 117.0 40.0 \
    --start-date 2024-06-01 \
    --end-date 2024-06-30 \
    --output-dir ./gpm_data
```

## 数据源 / Data Source

| 来源 | URL | 凭证 |
|---|---|---|
| **NASA GES DISC**（默认） | `https://disc.gsfc.nasa.gov/` | 无 |

> **License** — GPM IMERG 数据由 NASA 发布，**公共领域**。

## 支持的产品 / Supported Products

| 产品 | 说明 | 分辨率 |
|---|---|---|
| **GPM_3IMERGDL** | IMERG Late Run 日降水 | 0.1° (~10km) |
| **GPM_3IMERGM** | IMERG 月降水 | 0.1° (~10km) |

## 支持的变量 / Variables

| 变量 | 说明 |
|---|---|
| `precipitationCal` | 校准后降水估计 (mm/hr) |
| `precipitation` | 未校准降水 (mm/hr) |
| `randomError` | 随机误差估计 (mm/hr) |

## 参数一览 / Parameters

| 参数 | 说明 | 必填 |
|---|---|---|
| `--bbox` | 地理范围 `[minLon minLat maxLon maxLat]` | ❌ |
| `--start-date` | 开始日期 `YYYY-MM-DD` | ✅ |
| `--end-date` | 结束日期 `YYYY-MM-DD` | ✅ |
| `--variables` | 变量列表（默认 `precipitationCal`） | ❌ |
| `--download` | 触发实际下载 | ❌ |
| `--output-dir` | 下载目录（默认 `./gpm_data`） | ❌ |

## License

MIT-0（详见 [LICENSE](./LICENSE)）。
GPM IMERG 数据 © NASA，公共领域。
