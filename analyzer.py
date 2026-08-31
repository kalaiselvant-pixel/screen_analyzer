"""
Double Proctoring Analyzer — Full Pipeline
Orchestrates BOTH webcam proctoring AND screen analysis simultaneously.
"""

import cv2
import numpy as np
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Callable
import logging

from models.overlay_detector import OverlayDetector
from models.screen_change_detector import ScreenChangeDetector
from models.ui_element_detector import UIElementDetector
from models.ocr_analyzer import OCRAnalyzer
from models.process_monitor import ProcessMonitor
from models.webcam_proctoring import WebcamProctor
from models.audio_detector import AudioAnomalyDetector
from models.yolo_detector import YoloProctorDetector
from utils.report_generator import ReportGenerator
from utils.frame_processor import FrameProcessor
from utils.incident_tracker import IncidentTracker
from utils.periodic_capture import PeriodicCapture

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class ScreenAnalyzer:
    """Full Double Proctoring Engine — mode: screen | webcam | full"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or self._default_config()
        self.output_dir = Path(self.config["output_dir"])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "screenshots").mkdir(exist_ok=True)

        self.overlay_detector       = OverlayDetector(self.config)
        self.screen_change_detector = ScreenChangeDetector(self.config)
        self.ui_detector            = UIElementDetector(self.config)
        self.ocr_analyzer           = OCRAnalyzer(self.config)
        self.process_monitor        = ProcessMonitor(self.config)
        self.webcam_proctoring      = WebcamProctor(self.config)
        self.audio_detector         = AudioAnomalyDetector(self.config)
        self.yolo_detector          = YoloProctorDetector(self.config)
        self.incident_tracker       = IncidentTracker(self.config)
        self.report_generator       = ReportGenerator(self.output_dir)
        self.frame_processor        = FrameProcessor(self.config)
        self.periodic_capture       = PeriodicCapture(self.config, self.output_dir)
        logger.info(f"DoubleProctor initialized — mode={self.config.get('mode','full')}")

    def _default_config(self) -> dict:
        return {
            "output_dir": "output", "mode": "full",
            "frame_sample_rate": 2,
            "overlay_confidence_threshold": 0.55,
            "change_threshold": 0.30, "popup_area_ratio": 0.05,
            "min_incident_duration": 0.5,
            "absence_threshold_sec": 3.0, "gaze_away_threshold": 3.0,
            "head_yaw_threshold_deg": 25, "head_pitch_threshold_deg": 20,
            "head_away_threshold_sec": 3.0, "phone_threshold_sec": 2.0,
            "ocr_min_interval_sec": 5.0,
            "process_check_interval_sec": 10.0,
            "silence_threshold_sec": 30.0,
            "resize_width": 1280,
            "model_name": "yolov8n.pt",
            "save_annotated_frames": True, "draw_bounding_boxes": True,
            "periodic_screenshot_interval_sec": 30.0,
        }

    def analyze(
        self,
        video_path: str,
        webcam_path: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> dict:
        video_path = Path(video_path)
        if not video_path.exists():
            return {"status": "error", "message": f"Video not found: {video_path}"}

        logger.info(f"Analyzing: {video_path}")
        start_time = time.time()
        mode = self.config.get("mode", "full")

        # Audio analysis
        audio_violations = []
        if mode in ("full",):
            if self.audio_detector.load_audio_from_video(str(video_path)):
                audio_violations = self.audio_detector.analyze()

        screen_cap = cv2.VideoCapture(str(video_path))
        webcam_cap = None
        if webcam_path:
            wcp = Path(webcam_path)
            if wcp.exists():
                webcam_cap = cv2.VideoCapture(str(wcp))

        if not screen_cap.isOpened():
            return {"status": "error", "message": "Could not open video file."}

        fps = screen_cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(screen_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        sample_rate = max(1, int(fps / self.config["frame_sample_rate"]))
        logger.info(f"{total_frames} frames @ {fps:.1f}fps, sampling every {sample_rate}")

        if progress_callback:
            progress_callback(0.0, "Starting analysis…")

        baseline_frame = None
        frame_idx = 0

        while True:
            ret, screen_frame = screen_cap.read()
            if not ret:
                break
            frame_idx += 1

            webcam_frame = None
            if webcam_cap:
                wret, webcam_frame = webcam_cap.read()
                if not wret:
                    webcam_frame = None

            if frame_idx % sample_rate != 0:
                continue

            timestamp = frame_idx / fps
            screen_frame = self.frame_processor.preprocess(screen_frame)

            if baseline_frame is None:
                baseline_frame = screen_frame.copy()
                self.screen_change_detector.set_baseline(baseline_frame)
                continue

            self.periodic_capture.maybe_capture(screen_frame, timestamp)

            detections = []

            if mode in ("screen", "full"):
                change = self.screen_change_detector.detect(screen_frame, timestamp)
                if change: detections.append(change)
                detections.extend(self.overlay_detector.detect(screen_frame, baseline_frame))
                detections.extend(self.ui_detector.detect(screen_frame, baseline_frame))
                detections.extend(self.ocr_analyzer.detect(screen_frame, timestamp))

            if mode in ("webcam", "full"):
                cam = webcam_frame if webcam_frame is not None else screen_frame
                detections.extend(self.webcam_proctoring.detect(cam, timestamp))
                detections.extend(self.yolo_detector.detect(cam, timestamp))

            detections.extend(self.process_monitor.detect(screen_frame, timestamp))

            for det in detections:
                screenshot_path = None
                if self._should_save_screenshot(det):
                    screenshot_path = self._save_screenshot(screen_frame, frame_idx, det, timestamp)
                self.incident_tracker.record(det, timestamp, screenshot_path)

            self.screen_change_detector.update_baseline(screen_frame, timestamp)

            if progress_callback and total_frames > 0:
                progress_callback(frame_idx / total_frames,
                                  f"Analyzing frame {frame_idx}/{total_frames}")

        screen_cap.release()
        if webcam_cap: webcam_cap.release()

        video_violations = self.incident_tracker.finalize()
        all_violations = sorted(video_violations + audio_violations,
                                key=lambda v: v.get("start_time", "00:00:00"))

        elapsed = time.time() - start_time
        report = self.report_generator.generate(
            violations=all_violations,
            video_path=str(video_path),
            video_duration=duration,
            frames_analyzed=frame_idx // sample_rate,
            processing_time=elapsed,
            audit_captures=self.periodic_capture.get_captures(),
            mode=mode,
            pdf_path=self.config.get("pdf_path"),
            sample_fps=self.config.get("frame_sample_rate"),
            model_name=self.config.get("model_name"),
        )
        if progress_callback: progress_callback(1.0, "Analysis complete.")
        logger.info(f"Done in {elapsed:.1f}s — violations: {len(all_violations)}")
        return report

    def _should_save_screenshot(self, detection: dict) -> bool:
        """Keep evidence for all accepted YOLO proctoring detections."""
        yolo_types = {
            "extra_device_detected", "multiple_people", "phone_detected",
        }
        threshold = self.config.get("overlay_confidence_threshold", 0.55)
        if detection.get("type") in yolo_types:
            threshold = self.config.get("yolo_confidence_threshold", 0.35)
        return detection.get("confidence", 0) >= threshold

    def _save_screenshot(self, frame, frame_idx, detection, timestamp) -> str:
        annotated = frame.copy()
        if self.config.get("draw_bounding_boxes") and "bbox" in detection:
            color = self._violation_color(detection["type"])
            annotations = detection.get("annotations", [detection])
            for item in annotations:
                x, y, w, h = item["bbox"]
                confidence = item.get("confidence", detection.get("confidence", 0))
                cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 3)
                label = f"{detection['type']} ({confidence:.0%})"
                cv2.putText(annotated, label, (x, max(y-10, 20)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
        ts_str = self._fmt(timestamp).replace(":", "-")
        fname = f"frame_{frame_idx:06d}_{detection['type']}_{ts_str}.png"
        path = self.output_dir / "screenshots" / fname
        cv2.imwrite(str(path), annotated)
        return str(path)

    @staticmethod
    def _violation_color(vtype):
        return {
            "overlay_detected": (0,0,255), "screen_switch": (0,140,255),
            "popup_detected": (0,255,255), "multiple_windows": (255,0,255),
            "ui_anomaly": (255,165,0), "absence_detected": (0,0,200),
            "multiple_persons": (0,0,180), "gaze_away": (180,0,255),
            "multiple_people": (0,0,180), "extra_device_detected": (0,165,255),
            "head_pose_violation": (255,80,0), "phone_detected": (0,200,50),
            "ai_tool_detected": (200,0,200), "cheating_site_detected": (220,0,0),
            "virtual_machine_detected": (100,0,200),
            "remote_desktop_detected": (150,0,200),
            "screen_share_detected": (80,80,220),
        }.get(vtype, (0,0,255))

    @staticmethod
    def _fmt(seconds):
        t = int(seconds)
        return f"{t//3600:02d}:{(t%3600)//60:02d}:{t%60:02d}"
