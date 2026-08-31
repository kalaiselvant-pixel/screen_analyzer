"""
Screen Change Detector
Detects abrupt screen switches (e.g., tab/application switching)
using Structural Similarity Index (SSIM) and histogram analysis.
"""

import cv2
import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)

try:
    from skimage.metrics import structural_similarity as ssim
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False
    logger.warning("scikit-image not found; using fallback SSIM implementation.")


class ScreenChangeDetector:
    """
    Detects sudden, significant screen content changes that indicate
    screen switching or application switching behavior.
    """

    def __init__(self, config: dict):
        self.config = config
        self.change_threshold = config.get("change_threshold", 0.30)
        self.baseline: Optional[np.ndarray] = None
        self.previous_frame: Optional[np.ndarray] = None
        self.last_significant_change_time: float = -10.0
        self.baseline_update_interval: float = 30.0  # Update baseline every 30s
        self.last_baseline_update: float = 0.0
        self.change_history = []  # Rolling window for smoothing

    def set_baseline(self, frame: np.ndarray):
        """Set the initial clean baseline frame."""
        self.baseline = frame.copy()
        self.previous_frame = frame.copy()
        logger.debug("Baseline set.")

    def detect(self, frame: np.ndarray, timestamp: float) -> Optional[dict]:
        """
        Compare current frame against previous frame for abrupt changes.

        Returns detection dict if screen switch is detected, else None.
        """
        if self.previous_frame is None:
            self.previous_frame = frame.copy()
            return None

        # Compute similarity between consecutive frames
        sim_score = self._compute_similarity(frame, self.previous_frame)
        change_magnitude = 1.0 - sim_score

        self.change_history.append(change_magnitude)
        if len(self.change_history) > 5:
            self.change_history.pop(0)

        # Smooth over recent frames to reduce false positives
        smoothed_change = np.mean(self.change_history)

        self.previous_frame = frame.copy()

        # Ignore if too close to the last detected change (debounce)
        if timestamp - self.last_significant_change_time < 2.0:
            return None

        if smoothed_change > self.change_threshold:
            self.last_significant_change_time = timestamp
            confidence = self._change_to_confidence(smoothed_change)

            # Additional check: histogram comparison
            hist_diff = self._histogram_difference(frame, self.baseline)
            if hist_diff > 0.4:
                confidence = min(0.98, confidence + 0.1)

            logger.debug(f"Screen switch @ {timestamp:.1f}s: change={smoothed_change:.3f}, conf={confidence:.3f}")

            return {
                "type": "screen_switch",
                "confidence": round(confidence, 3),
                "change_magnitude": round(float(smoothed_change), 3),
                "histogram_diff": round(float(hist_diff), 3),
                "description": f"Abrupt screen switch detected (change={smoothed_change:.1%})",
                # No bbox for full-screen switch
            }

        return None

    def update_baseline(self, frame: np.ndarray, timestamp: float):
        """
        Gradually update baseline to account for legitimate content changes
        (e.g., video playing in the interview window).
        Only updates if the frame is similar enough to current baseline.
        """
        if timestamp - self.last_baseline_update < self.baseline_update_interval:
            return

        if self.baseline is None:
            return

        sim = self._compute_similarity(frame, self.baseline)
        # Only update if reasonably similar (not a violating frame)
        if sim > 0.65:
            alpha = 0.15  # Slow drift
            self.baseline = cv2.addWeighted(self.baseline, 1 - alpha, frame, alpha, 0)
            self.last_baseline_update = timestamp
            logger.debug(f"Baseline updated at {timestamp:.1f}s (sim={sim:.3f})")

    def _compute_similarity(self, f1: np.ndarray, f2: np.ndarray) -> float:
        """Compute structural similarity between two frames."""
        if f1.shape != f2.shape:
            f2 = cv2.resize(f2, (f1.shape[1], f1.shape[0]))

        gray1 = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY)

        if SKIMAGE_AVAILABLE:
            score, _ = ssim(gray1, gray2, full=True)
            return float(score)
        else:
            return self._fallback_ssim(gray1, gray2)

    @staticmethod
    def _fallback_ssim(img1: np.ndarray, img2: np.ndarray) -> float:
        """Simplified SSIM fallback using correlation coefficient."""
        img1 = img1.astype(np.float64)
        img2 = img2.astype(np.float64)

        mu1, mu2 = img1.mean(), img2.mean()
        sigma1 = img1.std()
        sigma2 = img2.std()
        sigma12 = ((img1 - mu1) * (img2 - mu2)).mean()

        C1 = (0.01 * 255) ** 2
        C2 = (0.03 * 255) ** 2

        num = (2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)
        den = (mu1**2 + mu2**2 + C1) * (sigma1**2 + sigma2**2 + C2)

        return float(num / den) if den != 0 else 1.0

    @staticmethod
    def _histogram_difference(f1: np.ndarray, f2: np.ndarray) -> float:
        """Compare color histograms for a coarse global difference measure."""
        diff_scores = []
        for ch in range(3):
            h1 = cv2.calcHist([f1], [ch], None, [64], [0, 256])
            h2 = cv2.calcHist([f2], [ch], None, [64], [0, 256])
            h1 = cv2.normalize(h1, h1).flatten()
            h2 = cv2.normalize(h2, h2).flatten()
            score = cv2.compareHist(h1, h2, cv2.HISTCMP_BHATTACHARYYA)
            diff_scores.append(score)
        return float(np.mean(diff_scores))

    @staticmethod
    def _change_to_confidence(change: float) -> float:
        """Map change magnitude to confidence score."""
        # Sigmoid-like mapping
        if change < 0.30:
            return 0.0
        elif change < 0.50:
            return 0.5 + (change - 0.30) * 2.0
        else:
            return min(0.97, 0.90 + (change - 0.50) * 0.35)
