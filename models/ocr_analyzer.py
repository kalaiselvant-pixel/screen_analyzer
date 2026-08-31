"""
OCR Screen Analyzer
Uses Tesseract OCR to extract and analyze text from screen frames.
Flags:
 - AI tool keywords (ChatGPT, Claude, Gemini, Copilot…)
 - Cheating-related content (answers, solutions, code sharing sites)
 - Copy-paste indicators
"""

import cv2
import numpy as np
from typing import List, Optional
import logging
import re

logger = logging.getLogger(__name__)

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("pytesseract not found – OCR analysis disabled.")

# ── Suspicious keyword categories ─────────────────────────────────────────
AI_TOOLS = [
    "chatgpt", "openai", "claude", "anthropic", "gemini", "copilot",
    "bard", "perplexity", "grok", "llm", "ai assistant", "chat.openai",
]

CHEAT_SITES = [
    "chegg", "coursehero", "bartleby", "studyblue", "quizlet",
    "stackoverflow", "github", "pastebin", "codeshare",
    "answers.com", "brainly",
]

SOLUTION_KEYWORDS = [
    "solution", "answer key", "solved", "cheat sheet",
    "def solve", "def answer", "# answer", "return result",
]

COPY_PASTE_PATTERNS = [
    r"ctrl\s*\+\s*[cv]",
    r"command\s*\+\s*[cv]",
    r"copied\s+to\s+clipboard",
]

ALL_SUSPICIOUS = AI_TOOLS + CHEAT_SITES + SOLUTION_KEYWORDS


class OCRAnalyzer:
    """
    Performs periodic OCR on screen frames and flags suspicious text content.
    OCR is expensive — runs only every N frames (configurable).
    """

    def __init__(self, config: dict):
        self.config = config
        self.threshold = config.get("overlay_confidence_threshold", 0.55)
        self.ocr_interval_frames = config.get("ocr_interval_frames", 45)
        self._frame_counter = 0
        self._last_text = ""
        self._last_ocr_timestamp = -99.0
        self._ocr_min_interval = config.get("ocr_min_interval_sec", 5.0)

    def detect(self, frame: np.ndarray, timestamp: float) -> List[dict]:
        """Run OCR if enough time has passed. Returns violation list."""
        self._frame_counter += 1
        detections = []

        if not OCR_AVAILABLE:
            return detections

        if (timestamp - self._last_ocr_timestamp) < self._ocr_min_interval:
            return detections

        self._last_ocr_timestamp = timestamp

        text = self._extract_text(frame)
        if not text or len(text.strip()) < 10:
            return detections

        self._last_text = text

        # Run keyword analysis
        detections.extend(self._check_keywords(text, timestamp, frame))
        detections.extend(self._check_copy_paste(text, timestamp, frame))

        return detections

    def _extract_text(self, frame: np.ndarray) -> str:
        """Preprocess frame and run Tesseract OCR."""
        try:
            # Convert to grayscale + upscale for better OCR accuracy
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape

            # Adaptive threshold for varied backgrounds
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )

            # Tesseract config: fast mode, assume single block of text
            config = "--oem 3 --psm 11"
            text = pytesseract.image_to_string(thresh, config=config)
            return text.lower()

        except Exception as e:
            logger.debug(f"OCR error: {e}")
            return ""

    def _check_keywords(self, text: str, timestamp: float, frame: np.ndarray) -> List[dict]:
        """Check extracted text for suspicious keyword categories."""
        detections = []
        found_ai = [kw for kw in AI_TOOLS if kw in text]
        found_cheat = [kw for kw in CHEAT_SITES if kw in text]
        found_solution = [kw for kw in SOLUTION_KEYWORDS if kw in text]

        if found_ai:
            confidence = min(0.96, 0.75 + len(found_ai) * 0.07)
            detections.append({
                "type": "ai_tool_detected",
                "confidence": round(confidence, 3),
                "keywords": found_ai[:5],
                "description": f"AI tool content detected: {', '.join(found_ai[:3])}",
            })

        if found_cheat:
            confidence = min(0.95, 0.72 + len(found_cheat) * 0.08)
            detections.append({
                "type": "cheating_site_detected",
                "confidence": round(confidence, 3),
                "keywords": found_cheat[:5],
                "description": f"Cheating site detected: {', '.join(found_cheat[:3])}",
            })

        if found_solution:
            confidence = min(0.88, 0.60 + len(found_solution) * 0.06)
            detections.append({
                "type": "solution_content_detected",
                "confidence": round(confidence, 3),
                "keywords": found_solution[:5],
                "description": f"Solution content keywords: {', '.join(found_solution[:3])}",
            })

        return detections

    def _check_copy_paste(self, text: str, timestamp: float, frame: np.ndarray) -> List[dict]:
        """Check for copy-paste indicators."""
        detections = []
        for pattern in COPY_PASTE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                detections.append({
                    "type": "copy_paste_detected",
                    "confidence": 0.80,
                    "description": "Copy/paste keyboard shortcut visible on screen",
                })
                break
        return detections

    def get_last_text(self) -> str:
        return self._last_text
