# Repository Guidelines

## Project Structure & Module Organization

`main.py` is the command-line entry point and `analyzer.py` coordinates the
double-proctoring pipeline. Detection features live in `models/` (for example,
`overlay_detector.py`, `webcam_proctoring.py`, and `audio_detector.py`). Shared
frame processing, incident grouping, periodic capture, and report generation
belong in `utils/`. Keep detector-specific logic out of the orchestrator where
possible. Put pytest tests in `tests/`; mirror the module being tested, such as
`tests/test_overlay_detector.py`. `output/` contains runtime reports,
screenshots, and audit artifacts; treat it as generated evidence, not source.

## Build, Test, and Development Commands

Create an isolated environment, then install the pinned minimum dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run an analysis with `python main.py interview.mp4`. Use a separate result
directory while developing, for example
`python main.py interview.mp4 --output results --fps 3 --threshold 0.6`.
Run the test suite with `pytest tests/ -v`; add `--cov` when checking coverage,
for example `pytest tests/ -v --cov=models --cov=utils`.

## Coding Style & Naming Conventions

Use four-space indentation, standard-library imports before third-party imports,
and `snake_case` for files, functions, variables, and configuration keys.
Use `PascalCase` for classes, following names such as `ScreenAnalyzer` and
`OverlayDetector`. Keep type hints on public methods and return detector output
as the established dictionaries (`type`, `confidence`, `bbox`, `description`).
No formatter or linter is configured; preserve the surrounding style and keep
changes focused.

## Testing Guidelines

Use pytest and name files `test_*.py` and test functions `test_*`. Test
detectors with deterministic NumPy/OpenCV fixture frames rather than depending
on large video files. Cover both detection and no-detection paths, threshold
boundaries, and report/incident output contracts. Do not commit generated
screenshots or reports solely to demonstrate a test run.

## Commit & Pull Request Guidelines

Git history is unavailable in this checkout, so use concise imperative commits,
such as `Add OCR confidence threshold` or `Fix incident merge timing`. Keep each
commit scoped to one change. Pull requests should state the affected detection
mode, configuration changes, and verification command; include representative
report or screenshot output when a user-visible detection behavior changes.

## Configuration & Privacy

Review threshold changes against representative recordings. Videos, screenshots,
audio, and generated reports may contain sensitive candidate data; keep them out
of commits and redact material before attaching it to an issue or pull request.
