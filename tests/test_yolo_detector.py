from types import SimpleNamespace

import numpy as np

from models.yolo_detector import YoloProctorDetector


class FakeBox:
    def __init__(self, class_id, confidence, coordinates):
        self.cls = np.array([class_id])
        self.conf = np.array([confidence])
        self.xyxy = np.array([coordinates])


class FakeModel:
    def predict(self, *args, **kwargs):
        boxes = [
            FakeBox(63, 0.82, [10, 10, 90, 70]),
            FakeBox(0, 0.91, [20, 20, 100, 180]),
            FakeBox(0, 0.78, [150, 30, 230, 190]),
            FakeBox(67, 0.67, [120, 120, 150, 170]),
        ]
        return [SimpleNamespace(boxes=boxes)]


def test_yolo_detector_creates_proctoring_incidents() -> None:
    detector = YoloProctorDetector({"yolo_enabled": True})
    detector._model = FakeModel()
    detections = detector.detect(np.zeros((240, 320, 3), dtype=np.uint8), 2.0)

    assert [item["type"] for item in detections] == [
        "extra_device_detected", "multiple_people", "phone_detected"
    ]
    assert len(detections[1]["annotations"]) == 2
