# MingLi Agent V2.0 Runbook

## Install

```bash
python -m pip install -e ".[dev]"
python -c "import mingli; print(mingli.__file__)"
```

The printed import path must be inside the intended checkout. Wheel readback must use a new virtual environment and `python -I`.

## Run

```bash
python -m mingli.phase23_cli run --input examples/runtime_input.json
python -m mingli.phase24_cli assess
python -m mingli.phase24_cli benchmark
```

## Validate

```bash
python -m compileall -q src tests
python -m unittest discover -v
python -m pytest -q
python -m build
git diff --check
```

Then run P16–P24 `validate`/`benchmark` commands exposed by each CLI. A technical RC additionally requires source-tree and isolated-wheel canonical hashes to match.

## Troubleshooting

- Import path points elsewhere: remove stale editable installs or set `PYTHONPATH=src` for source verification; use a clean venv for wheel verification.
- `baseline_domains` rejected: remove it; P23 derives baselines from P16.
- Annual evidence rejected: supply `evidence_id`, `source_type`, and `source_id`; reality overrides also require `verified=true`.
- Product remains on hold: this is expected until verse review and authorized real-case thresholds close.
