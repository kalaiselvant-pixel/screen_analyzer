"""
Frame Processor
Handles frame preprocessing: resizing, normalization, denoising.
"""

import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


class FrameProcessor:
    def __init__(self, config: dict):
        self.max_width = config.get("resize_width", 1280)
        self._scale = None

    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Resize frame if necessary and apply light denoising."""
        h, w = frame.shape[:2]

        if w > self.max_width:
            scale = self.max_width / w
            new_w = int(w * scale)
            new_h = int(h * scale)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            if self._scale is None:
                self._scale = scale
                logger.debug(f"Frame resized: {w}x{h} → {new_w}x{new_h}")

        # Light bilateral filter to reduce compression artifacts
        frame = cv2.bilateralFilter(frame, 5, 25, 25)
        return frame
