from pathlib import Path

import pytest
from PIL import Image

from utils.report_generator import ReportGenerator


def test_generate_creates_pdf_report(tmp_path: Path) -> None:
    pytest.importorskip("reportlab")
    pdf_path = tmp_path / "candidate_report.pdf"
    screenshot_path = tmp_path / "evidence.png"
    Image.new("RGB", (160, 90), "navy").save(screenshot_path)
    report = ReportGenerator(tmp_path).generate(
        violations=[{
            "type": "overlay_detected",
            "start_time": "00:00:10",
            "end_time": "00:00:12",
            "duration": "2.0s",
            "confidence": 0.83,
            "description": "An overlay was detected.",
            "screenshot": str(screenshot_path),
        }],
        video_path="candidate_session.mp4",
        video_duration=120.0,
        frames_analyzed=240,
        processing_time=15.5,
        pdf_path=pdf_path,
    )

    pdf_path = Path(report["report_pdf"])
    assert pdf_path.name == "candidate_report.pdf"
    assert pdf_path.is_file()
    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert report["risk_level"] == "LOW"
