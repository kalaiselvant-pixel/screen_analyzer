"""
Periodic Screenshot Capture
Saves clean, full-resolution screenshots at configurable intervals
regardless of whether a violation was detected.
Used as audit trail for the proctoring session.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


class PeriodicCapture:
    """
    Saves a screenshot every N seconds as an audit trail.
    Stored separately from violation screenshots.
    """

    def __init__(self, config: dict, output_dir: Path):
        self.interval = config.get("periodic_screenshot_interval_sec", 30.0)
        self.audit_dir = output_dir / "audit_trail"
        self.audit_dir.mkdir(exist_ok=True)
        self._last_capture = -999.0
        self._capture_count = 0
        self.captures = []  # List of {timestamp, path}

    def maybe_capture(self, frame: np.ndarray, timestamp: float) -> Optional[str]:
        """Save a screenshot if the interval has elapsed. Returns path or None."""
        if (timestamp - self._last_capture) < self.interval:
            return None

        self._last_capture = timestamp
        self._capture_count += 1
        ts_str = self._fmt(timestamp).replace(":", "-")
        filename = f"audit_{self._capture_count:04d}_{ts_str}.jpg"
        path = self.audit_dir / filename

        # Save at 85% JPEG quality (smaller files, still readable)
        cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        self.captures.append({"timestamp": self._fmt(timestamp), "path": str(path)})
        logger.debug(f"Audit screenshot: {filename}")
        return str(path)

    def get_captures(self):
        return self.captures

    @staticmethod
    def _fmt(seconds: float) -> str:
        td = timedelta(seconds=int(seconds))
        t = int(td.total_seconds())
        return f"{t//3600:02d}:{(t%3600)//60:02d}:{t%60:02d}"
