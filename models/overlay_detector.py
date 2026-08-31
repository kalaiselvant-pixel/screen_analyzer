"""
Overlay Detector
Detects multiple windows, overlays, and UI interruptions using
contour analysis, edge detection, and structural similarity.
"""

import cv2
import numpy as np
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class OverlayDetector:
    """
    Detects visual overlays on top of the primary interview screen.
    Uses edge-based contour analysis and structural comparison.
    """

    def __init__(self, config: dict):
        self.config = config
        self.threshold = config.get("overlay_confidence_threshold", 0.55)
        self.popup_area_ratio = config.get("popup_area_ratio", 0.05)

    def detect(self, frame: np.ndarray, baseline: np.ndarray) -> List[dict]:
        """
        Detect overlay elements by comparing current frame with baseline.

        Returns list of detection dicts with type, confidence, bbox.
        """
        detections = []

        # Method 1: Rectangular overlay detection via contour analysis
        overlay_detections = self._detect_rectangular_overlays(frame, baseline)
        detections.extend(overlay_detections)

        # Method 2: Window border / frame-within-frame detection
        window_detections = self._detect_window_borders(frame)
        detections.extend(window_detections)

        # Method 3: High-contrast sudden region detection
        popup_detections = self._detect_popup_regions(frame, baseline)
        detections.extend(popup_detections)

        return detections

    def _detect_rectangular_overlays(self, frame: np.ndarray, baseline: np.ndarray) -> List[dict]:
        """Find large rectangular regions that differ significantly from baseline."""
        detections = []
        h, w = frame.shape[:2]

        # Compute absolute difference
        diff = cv2.absdiff(frame, baseline)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)

        # Morphological closing to connect nearby regions
        kernel = np.ones((15, 15), np.uint8)
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        frame_area = h * w

        for cnt in contours:
            area = cv2.contourArea(cnt)
            area_ratio = area / frame_area

            # Must be significant but not the full screen
            if area_ratio < self.popup_area_ratio or area_ratio > 0.95:
                continue

            x, y, rw, rh = cv2.boundingRect(cnt)
            aspect = rw / max(rh, 1)

            # Rectangular shapes typical of windows
            if 0.2 < aspect < 5.0:
                # Check internal structure - real windows have non-uniform content
                roi_diff = gray_diff[y:y+rh, x:x+rw]
                mean_diff = roi_diff.mean()
                std_diff = roi_diff.std()

                # High mean + high std = significant structured overlay
                confidence = self._compute_overlay_confidence(
                    area_ratio, mean_diff, std_diff
                )

                if confidence >= self.threshold:
                    detections.append({
                        "type": "overlay_detected",
                        "confidence": confidence,
                        "bbox": (x, y, rw, rh),
                        "area_ratio": round(area_ratio, 3),
                        "description": f"Rectangular overlay covering {area_ratio:.1%} of screen",
                    })

        # Deduplicate overlapping boxes
        return self._deduplicate(detections)

    def _detect_window_borders(self, frame: np.ndarray) -> List[dict]:
        """Detect window-like structures via edge density patterns."""
        detections = []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Detect strong horizontal and vertical edges (window borders)
        edges = cv2.Canny(gray, 50, 150)
        
        # Dilate to connect border lines
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=2)

        # Find rectangular contours that look like window frames
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

            # 4-sided polygon = likely window
            if len(approx) == 4:
                x, y, rw, rh = cv2.boundingRect(approx)
                area_ratio = (rw * rh) / (w * h)

                if 0.08 < area_ratio < 0.85:
                    # Check for title-bar-like region at top
                    title_bar_region = gray[y:y+max(30, rh//10), x:x+rw]
                    if title_bar_region.size > 0:
                        tb_std = title_bar_region.std()
                        # Require higher edge density to reduce false positives
                        # from content elements like video boxes
                        edge_density = edges[y:y+rh, x:x+rw].mean() / 255.0
                        if edge_density < 0.08:
                            continue
                        confidence = min(0.95, 0.45 + (area_ratio * 0.25) + (tb_std / 220) + edge_density * 0.3)

                        if confidence >= self.threshold:
                            detections.append({
                                "type": "multiple_windows",
                                "confidence": round(confidence, 3),
                                "bbox": (x, y, rw, rh),
                                "area_ratio": round(area_ratio, 3),
                                "description": "Window-like border structure detected",
                            })

        return self._deduplicate(detections)

    def _detect_popup_regions(self, frame: np.ndarray, baseline: np.ndarray) -> List[dict]:
        """Detect small popup windows and dialog boxes."""
        detections = []
        h, w = frame.shape[:2]

        diff = cv2.absdiff(frame, baseline)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray_diff, 40, 255, cv2.THRESH_BINARY)

        # Small kernel for popup detection
        kernel = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(thresh, kernel, iterations=3)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            area_ratio = area / (w * h)

            # Small to medium popup
            if 0.01 < area_ratio < 0.35:
                x, y, rw, rh = cv2.boundingRect(cnt)
                
                # Analyze region brightness change (dialogs often appear lighter/darker)
                roi_curr = frame[y:y+rh, x:x+rw]
                roi_base = baseline[y:y+rh, x:x+rw]
                
                brightness_diff = abs(
                    float(roi_curr.mean()) - float(roi_base.mean())
                )
                
                if brightness_diff > 15:
                    confidence = min(0.92, 0.45 + brightness_diff / 100 + area_ratio)

                    if confidence >= self.threshold:
                        detections.append({
                            "type": "popup_detected",
                            "confidence": round(confidence, 3),
                            "bbox": (x, y, rw, rh),
                            "area_ratio": round(area_ratio, 3),
                            "description": f"Popup/dialog box detected ({rw}x{rh}px)",
                        })

        return self._deduplicate(detections)

    def _compute_overlay_confidence(
        self, area_ratio: float, mean_diff: float, std_diff: float
    ) -> float:
        """Combine multiple signals into an overlay confidence score."""
        # Higher mean diff = more different from baseline
        diff_score = min(1.0, mean_diff / 80.0)
        # Higher std = structured content (not noise)
        struct_score = min(1.0, std_diff / 60.0)
        # Area score: overlays tend to be medium-sized
        area_score = 1.0 - abs(area_ratio - 0.3) / 0.5

        confidence = 0.4 * diff_score + 0.4 * struct_score + 0.2 * area_score
        return round(min(0.98, max(0.0, confidence)), 3)

    def _deduplicate(self, detections: List[dict], iou_threshold: float = 0.5) -> List[dict]:
        """Remove duplicate/overlapping detections using IoU."""
        if len(detections) <= 1:
            return detections

        kept = []
        used = set()

        for i, d in enumerate(detections):
            if i in used:
                continue
            best = d
            for j, d2 in enumerate(detections):
                if j <= i or j in used:
                    continue
                if "bbox" in d and "bbox" in d2:
                    if self._iou(d["bbox"], d2["bbox"]) > iou_threshold:
                        used.add(j)
                        if d2["confidence"] > best["confidence"]:
                            best = d2
            kept.append(best)

        return kept

    @staticmethod
    def _iou(b1: tuple, b2: tuple) -> float:
        x1, y1, w1, h1 = b1
        x2, y2, w2, h2 = b2
        ix = max(0, min(x1+w1, x2+w2) - max(x1, x2))
        iy = max(0, min(y1+h1, y2+h2) - max(y1, y2))
        inter = ix * iy
        union = w1*h1 + w2*h2 - inter
        return inter / union if union > 0 else 0.0
