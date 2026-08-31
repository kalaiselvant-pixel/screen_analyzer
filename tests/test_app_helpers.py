from pathlib import Path

from utils.ui_helpers import build_run_paths, slugify


def test_slugify_reduces_filename_noise():
    assert slugify("Interview Video 01") == "interview-video-01"


def test_build_run_paths_creates_pdf_in_ui_report_folder():
    paths = build_run_paths("Candidate Session.mp4")

    assert paths["run_dir"].parent == Path("output") / "ui_reports"
    assert paths["upload_path"].parent == Path("output") / "uploads"
    assert paths["pdf_path"].suffix == ".pdf"
    assert paths["run_name"].startswith("candidate-session_")
