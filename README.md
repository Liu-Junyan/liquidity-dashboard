# USD Liquidity Observatory

A Chinese-language dashboard for researching US dollar liquidity across four layers: 货币层, 离岸层, 信用层, and 金融市场层. GitHub Pages serves a static site built from FRED observations, Wind workbook exports, and same-date calculations.

| Guide | Use it to |
| --- | --- |
| [Architecture](docs/architecture.md) | Trace an observation from its source to a chart and identify which file owns a change. |
| [Data-source specification](docs/data-sources.md) | Look up an indicator's coverage, units, dates, calculation, and attribution. |
| [Operational runbook](docs/runbook.md) | Update inputs, test, publish, verify a release, or recover from a failure. The [maintenance tracker](docs/runbook.md#maintenance-tracker) records outstanding review findings. |

## Preview the saved production dashboard

From the repository root on macOS or Linux with Python 3.10 or later:

```sh
python3 scripts/build.py --mode production
python3 -m http.server 8000 --bind 127.0.0.1 --directory dist
```

Open <http://127.0.0.1:8000/>. This builds from the committed snapshot and works offline. For the synthetic dashboard, use `--mode demo`.
