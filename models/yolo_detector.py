"""YOLOv8 object detection for physical proctoring evidence."""

from typing import Dict, List, Optional
import logging

import numpy as np

logger = logging.getLogger(__name__)


class YoloProctorDetector:
    """Detect people, phones, and laptops in camera frames using COCO classes."""

    PERSON = 0
    CELL_PHONE = 67
    LAPTOP = 63

    def __init__(self, config: dict):
        self.enabled = config.get("yolo_enabled", True)
        self.model_name = config.get("yolo_model", "yolov8n.pt")
        self.confidence = config.get("yolo_confidence_threshold", 0.35)
        self._model = None
        self._load_attempted = False

    def detect(self, frame: np.ndarray, timestamp: float) -> List[dict]:
        if not self.enabled or not self._load_model():
            return []

        try:
            result = self._model.predict(
                frame,
                conf=self.confidence,
                classes=[self.PERSON, self.CELL_PHONE, self.LAPTOP],
                verbose=False,
            )[0]
        except Exception as exc:
            logger.warning("YOLO inference failed: %s", exc)
            return []

        objects = self._objects_from_result(result)
        persons = [item for item in objects if item["class_id"] == self.PERSON]
        phones = [item for item in objects if item["class_id"] == self.CELL_PHONE]
        laptops = [item for item in objects if item["class_id"] == self.LAPTOP]
        detections = []

        if laptops:
            detections.append(self._detection(
                "extra_device_detected", laptops,
                "{} laptop device(s) detected.".format(len(laptops)),
            ))
        if len(persons) > 1:
            detections.append(self._detection(
                "multiple_people", persons,
                "{} people detected in the camera frame.".format(len(persons)),
            ))
        if phones:
            detections.append(self._detection(
                "phone_detected", phones,
                "Mobile phone detected in the camera frame.",
            ))
        return detections

    def _load_model(self) -> bool:
        if self._model is not None:
            return True
        if self._load_attempted:
            return False
        self._load_attempted = True
        try:
            from ultralytics import YOLO

            self._model = YOLO(self.model_name)
            logger.info("YOLO proctor detector initialized with %s", self.model_name)
            return True
        except Exception as exc:
            logger.warning("YOLO is unavailable; object detection is disabled: %s", exc)
            return False

    @staticmethod
    def _objects_from_result(result) -> List[Dict]:
        if result.boxes is None:
            return []
        objects = []
        for box in result.boxes:
            x1, y1, x2, y2 = (int(value) for value in box.xyxy[0].tolist())
            objects.append({
                "class_id": int(box.cls[0].item()),
                "confidence": float(box.conf[0].item()),
                "bbox": (x1, y1, max(1, x2 - x1), max(1, y2 - y1)),
            })
        return objects

    @staticmethod
    def _detection(violation_type: str, objects: List[Dict], description: str) -> dict:
        best = max(objects, key=lambda item: item["confidence"])
        return {
            "type": violation_type,
            "confidence": best["confidence"],
            "bbox": best["bbox"],
            "annotations": objects,
            "description": description,
        }
