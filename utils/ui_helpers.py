from datetime import datetime
from pathlib import Path
import re


OUTPUT_ROOT = Path("output") / "ui_reports"
UPLOAD_ROOT = Path("output") / "uploads"


def ensure_runtime_dirs() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-").lower()
    return cleaned or "video"


def timestamp_label() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def build_run_paths(video_name: str) -> dict:
    stamp = timestamp_label()
    stem = slugify(Path(video_name).stem)
    run_name = f"{stem}_{stamp}"
    run_dir = OUTPUT_ROOT / run_name
    upload_path = UPLOAD_ROOT / f"{run_name}{Path(video_name).suffix.lower() or '.mp4'}"
    pdf_path = run_dir / f"{run_name}_report.pdf"
    return {
        "run_name": run_name,
        "run_dir": run_dir,
        "upload_path": upload_path,
        "pdf_path": pdf_path,
    }
