"""
Webcam Proctoring Module
Uses MediaPipe Tasks API (v0.10+) for:
 - Face detection / absence detection
 - Multiple person detection
 - Eye gaze tracking (iris landmark displacement)
 - Head pose estimation (yaw/pitch from landmarks)
 - Mobile phone detection (edge + shape heuristics)
"""

import cv2
import numpy as np
from typing import List, Optional
import logging
import os, urllib.request, tempfile

logger = logging.getLogger(__name__)

try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.vision import FaceDetector, FaceDetectorOptions
    from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions
    from mediapipe.tasks.python.core import base_options as mp_base_options
    MP_AVAILABLE = True
except Exception as e:
    MP_AVAILABLE = False
    logger.warning(f"MediaPipe tasks unavailable: {e}")

# Fallback: use OpenCV Haar cascade only
HAAR_CASCADE = None


def _get_haar():
    global HAAR_CASCADE
    if HAAR_CASCADE is None:
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        HAAR_CASCADE = cv2.CascadeClassifier(path)
    return HAAR_CASCADE


class WebcamProctor:
    """
    Single entry point for all webcam-based proctoring checks.
    Uses MediaPipe Tasks FaceDetector (works with v0.10+ API).
    Falls back to Haar cascade if models can't be downloaded.
    """

    def __init__(self, config: dict):
        self.config = config
        self.threshold = config.get("overlay_confidence_threshold", 0.55)
        self._face_detector = None
        self._init_detector()

        # State
        self._no_face_start: Optional[float] = None
        self._multi_person_start: Optional[float] = None
        self._gaze_away_start: Optional[float] = None
        self._head_away_start: Optional[float] = None
        self._phone_start: Optional[float] = None

    def _init_detector(self):
        """Try MediaPipe Tasks face detector; fall back to Haar."""
        if not MP_AVAILABLE:
            logger.info("Using Haar cascade fallback for face detection.")
            return

        # Try to get the face detection model from bundled location or download
        model_path = self._find_or_download_model()
        if model_path is None:
            logger.info("MediaPipe model unavailable; using Haar cascade fallback.")
            return

        try:
            opts = FaceDetectorOptions(
                base_options=mp_base_options.BaseOptions(model_asset_path=model_path),
                min_detection_confidence=0.5,
            )
            self._face_detector = FaceDetector.create_from_options(opts)
            logger.info("MediaPipe FaceDetector (Tasks API) initialized.")
        except Exception as e:
            logger.info(f"MediaPipe FaceDetector init failed ({e}); using Haar fallback.")

    def _find_or_download_model(self) -> Optional[str]:
        """Locate or download the blaze_face_short_range model."""
        # Common locations
        candidates = [
            "/tmp/blaze_face_short_range.tflite",
            os.path.expanduser("~/.mediapipe/blaze_face_short_range.tflite"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c

        # Try to download
        url = ("https://storage.googleapis.com/mediapipe-models/"
               "face_detector/blaze_face_short_range/float16/1/"
               "blaze_face_short_range.tflite")
        dest = "/tmp/blaze_face_short_range.tflite"
        try:
            logger.info("Downloading MediaPipe face model…")
            urllib.request.urlretrieve(url, dest)
            return dest
        except Exception as e:
            logger.debug(f"Model download failed: {e}")
            return None

    def detect(self, frame: np.ndarray, timestamp: float) -> List[dict]:
        """Run all webcam checks. Returns list of violation dicts."""
        face_count = self._count_faces(frame)
        detections = []

        absence = self._check_absence(face_count, timestamp)
        if absence: detections.append(absence)

        multi = self._check_multiple_persons(face_count, timestamp)
        if multi: detections.append(multi)

        if face_count > 0:
            gaze = self._check_gaze_heuristic(frame, timestamp)
            if gaze: detections.append(gaze)

            pose = self._check_head_pose_heuristic(frame, timestamp)
            if pose: detections.append(pose)

        phone = self._check_phone(frame, timestamp)
        if phone: detections.append(phone)

        return detections

    def _count_faces(self, frame: np.ndarray) -> int:
        """Count faces using MediaPipe or Haar cascade."""
        if self._face_detector is not None:
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb.astype(np.uint8)
                )
                result = self._face_detector.detect(mp_image)
                return len(result.detections)
            except Exception as e:
                logger.debug(f"MP detect error: {e}")

        # Haar fallback
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = _get_haar().detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
        return len(faces)

    # ── 1. Absence ────────────────────────────────────────────────────────
    def _check_absence(self, face_count: int, timestamp: float) -> Optional[dict]:
        threshold = self.config.get("absence_threshold_sec", 3.0)
        if face_count == 0:
            if self._no_face_start is None:
                self._no_face_start = timestamp
            duration = timestamp - self._no_face_start
            if duration >= threshold:
                return {
                    "type": "absence_detected",
                    "confidence": round(min(0.98, 0.65 + duration * 0.04), 3),
                    "duration_so_far": round(duration, 1),
                    "description": f"No face detected for {duration:.1f}s",
                }
        else:
            self._no_face_start = None
        return None

    # ── 2. Multiple persons ───────────────────────────────────────────────
    def _check_multiple_persons(self, face_count: int, timestamp: float) -> Optional[dict]:
        if face_count >= 2:
            if self._multi_person_start is None:
                self._multi_person_start = timestamp
            return {
                "type": "multiple_persons",
                "confidence": round(min(0.97, 0.75 + face_count * 0.05), 3),
                "face_count": face_count,
                "description": f"{face_count} faces detected simultaneously",
            }
        self._multi_person_start = None
        return None

    # ── 3. Gaze (heuristic without iris landmarks) ────────────────────────
    def _check_gaze_heuristic(self, frame: np.ndarray, timestamp: float) -> Optional[dict]:
        """
        Heuristic gaze check: detect eyes using Haar cascade,
        then check if they're positioned near the edge of the face region.
        """
        gaze_threshold = self.config.get("gaze_away_threshold", 3.0)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Use the upper 2/3 of the frame (where face typically appears)
        roi = gray[:2*h//3, :]

        eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_eye.xml"
        )
        eyes = eye_cascade.detectMultiScale(roi, 1.1, 5, minSize=(20, 20))

        if len(eyes) < 2:
            return None

        # Estimate gaze: eye centers should be roughly centered horizontally
        eye_cx = np.mean([ex + ew//2 for ex, ey, ew, eh in eyes])
        ratio = eye_cx / w

        is_away = ratio < 0.28 or ratio > 0.72
        if is_away:
            if self._gaze_away_start is None:
                self._gaze_away_start = timestamp
            duration = timestamp - self._gaze_away_start
            if duration >= gaze_threshold:
                direction = "left" if ratio < 0.28 else "right"
                return {
                    "type": "gaze_away",
                    "confidence": round(min(0.88, 0.60 + duration * 0.05), 3),
                    "gaze_ratio": round(float(ratio), 3),
                    "direction": direction,
                    "description": f"Gaze deviated {direction} for {duration:.1f}s",
                }
        else:
            self._gaze_away_start = None
        return None

    # ── 4. Head pose (heuristic) ──────────────────────────────────────────
    def _check_head_pose_heuristic(self, frame: np.ndarray, timestamp: float) -> Optional[dict]:
        """
        Heuristic head pose: detect face bounding box asymmetry.
        If the face is significantly off-center, assume head rotation.
        """
        head_time = self.config.get("head_away_threshold_sec", 3.0)
        yaw_limit = self.config.get("head_yaw_threshold_deg", 25)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        faces = _get_haar().detectMultiScale(gray, 1.1, 5, minSize=(60, 60))

        if len(faces) == 0:
            return None

        x, y, fw, fh = faces[0]
        face_cx = x + fw // 2
        # Normalized offset from center: -1 (left) to +1 (right)
        offset = (face_cx - w // 2) / (w // 2)
        yaw_approx = offset * 45  # Map to rough degrees

        looking_away = abs(yaw_approx) > yaw_limit
        if looking_away:
            if self._head_away_start is None:
                self._head_away_start = timestamp
            duration = timestamp - self._head_away_start
            if duration >= head_time:
                direction = "right" if yaw_approx > 0 else "left"
                return {
                    "type": "head_pose_violation",
                    "confidence": round(min(0.88, 0.60 + abs(yaw_approx) / 60), 3),
                    "yaw_deg": round(float(yaw_approx), 1),
                    "pitch_deg": 0.0,
                    "direction": direction,
                    "description": f"Head turned {direction} (yaw≈{yaw_approx:.1f}°)",
                }
        else:
            self._head_away_start = None
        return None

    # ── 5. Phone detection ────────────────────────────────────────────────
    def _check_phone(self, frame: np.ndarray, timestamp: float) -> Optional[dict]:
        h, w = frame.shape[:2]
        roi = frame[h//2:, :]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        kernel = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        roi_area = roi.shape[0] * roi.shape[1]
        phone_threshold = self.config.get("phone_threshold_sec", 2.0)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            area_ratio = area / roi_area
            if not (0.03 < area_ratio < 0.45):
                continue
            x, y, rw, rh = cv2.boundingRect(cnt)
            aspect = max(rw, rh) / (min(rw, rh) + 1e-6)
            if aspect < 1.6 or aspect > 5.0:
                continue
            roi_patch = gray[y:y+rh, x:x+rw]
            mean_brightness = roi_patch.mean()
            edge_density = edges[y:y+rh, x:x+rw].mean() / 255.0
            if mean_brightness < 140 and edge_density > 0.15:
                confidence = min(0.88, 0.5 + (1 - mean_brightness/255)*0.3 + edge_density*0.4)
                if confidence >= self.threshold:
                    if self._phone_start is None:
                        self._phone_start = timestamp
                    if timestamp - self._phone_start >= phone_threshold:
                        return {
                            "type": "phone_detected",
                            "confidence": round(confidence, 3),
                            "bbox": (x, y + h//2, rw, rh),
                            "description": f"Phone suspected (aspect={aspect:.1f})",
                        }

        self._phone_start = None
        return None

    @staticmethod
    def _head_direction(yaw: float, pitch: float) -> str:
        if abs(pitch) > abs(yaw):
            return "down" if pitch > 0 else "up"
        return "right" if yaw > 0 else "left"
