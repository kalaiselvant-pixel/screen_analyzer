"""
UI Element Detector
Detects suspicious UI elements: taskbars appearing, browser chrome,
notification panels, and other anomalous interface elements.
"""

import cv2
import numpy as np
from typing import List
import logging

logger = logging.getLogger(__name__)


class UIElementDetector:
    """
    Detects UI anomalies by analyzing screen regions for
    OS-level UI elements that shouldn't appear during normal interview sessions.
    """

    def __init__(self, config: dict):
        self.config = config
        self.threshold = config.get("overlay_confidence_threshold", 0.55)

    def detect(self, frame: np.ndarray, baseline: np.ndarray) -> List[dict]:
        """Run all UI element detection methods."""
        detections = []

        # Check for taskbar-like regions (horizontal bands at top/bottom)
        detections.extend(self._detect_taskbar_regions(frame, baseline))

        # Check for notification/toast popups (usually top-right corner)
        detections.extend(self._detect_notification_popups(frame, baseline))

        # Check for browser tab bar appearance
        detections.extend(self._detect_browser_ui(frame, baseline))

        # Check for chat window sidebars (vertical panels on edges)
        detections.extend(self._detect_side_panels(frame, baseline))

        return detections

    def _detect_taskbar_regions(self, frame: np.ndarray, baseline: np.ndarray) -> List[dict]:
        """Detect OS taskbars or top navigation bars appearing."""
        detections = []
        h, w = frame.shape[:2]

        regions = [
            ("top", frame[0:60, :], baseline[0:60, :], (0, 0, w, 60)),
            ("bottom", frame[h-60:h, :], baseline[h-60:h, :], (0, h-60, w, 60)),
        ]

        for label, roi, base_roi, bbox in regions:
            if roi.size == 0 or base_roi.size == 0:
                continue

            diff = cv2.absdiff(roi, base_roi)
            mean_diff = diff.mean()
            
            # Taskbars have many small elements -> high edge density
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray_roi, 30, 100)
            edge_density = edges.mean() / 255.0

            if mean_diff > 25 and edge_density > 0.05:
                confidence = min(0.95, 0.5 + mean_diff / 120 + edge_density * 0.5)
                if confidence >= self.threshold:
                    detections.append({
                        "type": "ui_anomaly",
                        "confidence": round(confidence, 3),
                        "bbox": bbox,
                        "area_ratio": round(60 * w / (h * w), 3),
                        "description": f"Taskbar/navigation bar detected at screen {label}",
                    })

        return detections

    def _detect_notification_popups(self, frame: np.ndarray, baseline: np.ndarray) -> List[dict]:
        """Detect notification toasts typically appearing in screen corners."""
        detections = []
        h, w = frame.shape[:2]

        corner_size_h = h // 5
        corner_size_w = w // 4

        corners = [
            ("top-right", frame[0:corner_size_h, w-corner_size_w:w],
             baseline[0:corner_size_h, w-corner_size_w:w],
             (w-corner_size_w, 0, corner_size_w, corner_size_h)),
            ("bottom-right", frame[h-corner_size_h:h, w-corner_size_w:w],
             baseline[h-corner_size_h:h, w-corner_size_w:w],
             (w-corner_size_w, h-corner_size_h, corner_size_w, corner_size_h)),
        ]

        for label, roi, base_roi, bbox in corners:
            if roi.size == 0 or base_roi.size == 0:
                continue

            diff = cv2.absdiff(roi, base_roi)
            mean_diff = float(diff.mean())
            
            # Check for rectangular bright regions (notification cards)
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, bright_mask = cv2.threshold(gray_roi, 200, 255, cv2.THRESH_BINARY)
            bright_ratio = bright_mask.mean() / 255.0

            if mean_diff > 30 and bright_ratio > 0.2:
                confidence = min(0.93, 0.5 + mean_diff / 100 + bright_ratio * 0.3)
                if confidence >= self.threshold:
                    detections.append({
                        "type": "popup_detected",
                        "confidence": round(confidence, 3),
                        "bbox": bbox,
                        "area_ratio": round((corner_size_h * corner_size_w) / (h * w), 3),
                        "description": f"Notification popup detected at {label}",
                    })

        return detections

    def _detect_browser_ui(self, frame: np.ndarray, baseline: np.ndarray) -> List[dict]:
        """Detect browser tab bars or address bars appearing."""
        detections = []
        h, w = frame.shape[:2]

        # Browser chrome typically appears as a ~40-80px horizontal band at top
        browser_region = frame[0:80, :]
        base_region = baseline[0:80, :]

        diff = cv2.absdiff(browser_region, base_region)
        diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(diff_gray, 20, 255, cv2.THRESH_BINARY)
        changed_ratio = thresh.mean() / 255.0

        if changed_ratio > 0.4:
            # Check for tab-like structures: repeated vertical lines in top band
            gray_top = cv2.cvtColor(browser_region, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray_top, 50, 150)
            
            # Count vertical edge segments (each tab separator)
            vert_profile = edges.sum(axis=0)
            peaks = np.where(vert_profile > edges.shape[0] * 0.3)[0]
            peak_count = len(peaks)

            if peak_count > 3:  # Multiple tab separators
                confidence = min(0.91, 0.55 + changed_ratio * 0.3 + peak_count * 0.02)
                if confidence >= self.threshold:
                    detections.append({
                        "type": "overlay_detected",
                        "confidence": round(confidence, 3),
                        "bbox": (0, 0, w, 80),
                        "area_ratio": round(80 / h, 3),
                        "description": "Browser tab bar / address bar detected",
                    })

        return detections

    def _detect_side_panels(self, frame: np.ndarray, baseline: np.ndarray) -> List[dict]:
        """Detect chat sidebars or side panels (common in AI assistant tools)."""
        detections = []
        h, w = frame.shape[:2]

        panel_width = w // 4

        sides = [
            ("left", frame[:, 0:panel_width], baseline[:, 0:panel_width], (0, 0, panel_width, h)),
            ("right", frame[:, w-panel_width:w], baseline[:, w-panel_width:w], (w-panel_width, 0, panel_width, h)),
        ]

        for label, roi, base_roi, bbox in sides:
            if roi.size == 0:
                continue

            diff = cv2.absdiff(roi, base_roi)
            diff_mean = float(diff.mean())

            # Side panels often have text -> check for horizontal edge patterns
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray_roi, 30, 90)
            horiz_profile = edges.sum(axis=1)
            
            # Consistent horizontal activity = text lines in a chat panel
            active_rows = np.sum(horiz_profile > roi.shape[1] * 0.05)
            active_ratio = active_rows / roi.shape[0]

            if diff_mean > 20 and active_ratio > 0.15:
                confidence = min(0.90, 0.45 + diff_mean / 80 + active_ratio * 0.4)
                if confidence >= self.threshold:
                    detections.append({
                        "type": "overlay_detected",
                        "confidence": round(confidence, 3),
                        "bbox": bbox,
                        "area_ratio": round(panel_width / w, 3),
                        "description": f"Side panel / chat window detected on {label}",
                    })

        return detections
