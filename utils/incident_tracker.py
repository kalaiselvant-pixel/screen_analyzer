"""
Incident Tracker
Groups raw frame-level detections into consolidated violation incidents
with start/end timestamps and duration.
"""

from typing import List, Optional, Dict
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class IncidentTracker:
    """
    Stateful tracker that merges consecutive detections of the same type
    into a single timed incident.
    """

    def __init__(self, config: dict):
        self.config = config
        self.min_duration = config.get("min_incident_duration", 0.5)
        self.merge_gap = 3.0  # Merge incidents within N seconds of same type
        # Ensure separate types tracked independently (always true via dict key)

        # Active incidents: type -> {start, end, screenshot, confidence, ...}
        self._active: Dict[str, dict] = {}
        self._completed: List[dict] = []

    def record(self, detection: dict, timestamp: float, screenshot_path: Optional[str]):
        """
        Record a detection at a given timestamp.
        Merges with active incident of same type if within gap window.
        """
        vtype = detection["type"]
        confidence = detection["confidence"]

        if vtype in self._active:
            active = self._active[vtype]
            # Extend if within merge window
            if timestamp - active["_last_seen"] <= self.merge_gap:
                active["end_time_sec"] = timestamp
                active["_last_seen"] = timestamp
                active["frames_flagged"] += 1
                active["confidence_total"] += confidence
                # Keep highest confidence screenshot
                if confidence > active["confidence"]:
                    active["confidence"] = confidence
                    if screenshot_path:
                        active["screenshot"] = screenshot_path
                return

            # Gap too large: finalize old, start new
            self._finalize(vtype)

        # Start new incident
        self._active[vtype] = {
            "type": vtype,
            "start_time_sec": timestamp,
            "end_time_sec": timestamp,
            "_last_seen": timestamp,
            "confidence": confidence,
            "frames_flagged": 1,
            "confidence_total": confidence,
            "screenshot": screenshot_path,
            "description": detection.get("description", ""),
        }

    def finalize(self) -> List[dict]:
        """Finalize all active incidents and return violation list."""
        for vtype in list(self._active.keys()):
            self._finalize(vtype)

        # Filter by minimum duration and format
        violations = []
        for inc in self._completed:
            duration = inc["end_time_sec"] - inc["start_time_sec"]
            if duration >= self.min_duration:
                violations.append(self._format_violation(inc, duration))

        # Sort by start time
        violations.sort(key=lambda v: v["start_time"])
        logger.info(f"Finalized {len(violations)} violations from {len(self._completed)} raw incidents.")
        return violations

    def _finalize(self, vtype: str):
        if vtype in self._active:
            self._completed.append(self._active.pop(vtype))

    @staticmethod
    def _format_violation(inc: dict, duration: float) -> dict:
        start = inc["start_time_sec"]
        end = inc["end_time_sec"]
        return {
            "start_time": IncidentTracker._fmt(start),
            "end_time": IncidentTracker._fmt(end),
            "duration": f"{duration:.1f}s",
            "duration_seconds": round(duration, 2),
            "type": inc["type"],
            "confidence": round(inc["confidence"], 3),
            "frames_flagged": inc.get("frames_flagged", 1),
            "avg_confidence": round(inc.get("confidence_total", inc["confidence"]) / inc.get("frames_flagged", 1), 3),
            "screenshot": inc.get("screenshot") or "N/A",
            "description": inc.get("description", ""),
        }

    @staticmethod
    def _fmt(seconds: float) -> str:
        td = timedelta(seconds=int(seconds))
        total = int(td.total_seconds())
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
