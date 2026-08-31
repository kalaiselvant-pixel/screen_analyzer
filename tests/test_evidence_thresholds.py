from analyzer import ScreenAnalyzer


def test_yolo_phone_evidence_uses_yolo_threshold() -> None:
    analyzer = ScreenAnalyzer.__new__(ScreenAnalyzer)
    analyzer.config = {
        "overlay_confidence_threshold": 0.55,
        "yolo_confidence_threshold": 0.35,
    }

    assert analyzer._should_save_screenshot({"type": "phone_detected", "confidence": 0.514})
    assert not analyzer._should_save_screenshot({"type": "phone_detected", "confidence": 0.34})


def test_non_yolo_evidence_keeps_general_threshold() -> None:
    analyzer = ScreenAnalyzer.__new__(ScreenAnalyzer)
    analyzer.config = {"overlay_confidence_threshold": 0.55}

    assert not analyzer._should_save_screenshot({"type": "overlay_detected", "confidence": 0.514})
