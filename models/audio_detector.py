"""
Audio Anomaly Detector
Extracts and analyzes audio track from video files.
Detects: multiple voices, background noise bursts, silence anomalies.
Uses OpenCV + scipy (no pyaudio needed for recorded video analysis).
"""

import cv2
import numpy as np
from typing import List, Optional
import logging
import struct
import wave
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)


class AudioAnomalyDetector:
    """
    Analyzes audio extracted from a video file.
    For recorded video proctoring (post-session analysis).
    """

    def __init__(self, config: dict):
        self.config = config
        self.threshold = config.get("overlay_confidence_threshold", 0.55)
        self._audio_available = False
        self._audio_data: Optional[np.ndarray] = None
        self._sample_rate: int = 16000

    def load_audio_from_video(self, video_path: str) -> bool:
        """
        Extract audio from video file using ffmpeg (if available).
        Returns True if audio was successfully extracted.
        """
        try:
            # Try ffmpeg extraction
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_wav = f.name

            result = subprocess.run(
                ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
                 "-ar", "16000", "-ac", "1", tmp_wav, "-y", "-loglevel", "error"],
                capture_output=True, timeout=60
            )

            if result.returncode == 0 and os.path.exists(tmp_wav):
                with wave.open(tmp_wav, 'rb') as wf:
                    frames = wf.readframes(wf.getnframes())
                    self._audio_data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                    self._sample_rate = wf.getframerate()
                os.unlink(tmp_wav)
                self._audio_available = True
                logger.info(f"Audio extracted: {len(self._audio_data)/self._sample_rate:.1f}s @ {self._sample_rate}Hz")
                return True

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            logger.debug(f"Audio extraction failed: {e}")

        self._audio_available = False
        return False

    def analyze(self) -> List[dict]:
        """
        Analyze extracted audio for anomalies.
        Returns list of timed violation dicts.
        """
        if not self._audio_available or self._audio_data is None:
            return []

        violations = []
        violations.extend(self._detect_multiple_voices())
        violations.extend(self._detect_sudden_noise())
        violations.extend(self._detect_suspicious_silence())
        return violations

    def _detect_multiple_voices(self) -> List[dict]:
        """
        Heuristic: detect periods with multiple simultaneous voice sources
        using spectral analysis. Multiple voices create more complex spectra.
        """
        violations = []
        if self._audio_data is None:
            return violations

        sr = self._sample_rate
        chunk_size = sr * 2  # 2-second windows
        hop_size = sr         # 1-second hop

        for start in range(0, len(self._audio_data) - chunk_size, hop_size):
            chunk = self._audio_data[start:start + chunk_size]
            rms = np.sqrt(np.mean(chunk**2))
            if rms < 0.01:  # Silence
                continue

            # FFT analysis
            fft = np.abs(np.fft.rfft(chunk))
            freqs = np.fft.rfftfreq(len(chunk), 1/sr)

            # Voice fundamental range: 80-300 Hz
            voice_mask = (freqs >= 80) & (freqs <= 300)
            voice_spectrum = fft[voice_mask]

            # Multiple voices → multiple peaks in fundamental range
            if len(voice_spectrum) > 10:
                # Count significant peaks
                mean_energy = voice_spectrum.mean()
                peaks = np.sum(voice_spectrum > mean_energy * 2.5)
                if peaks >= 3:  # 3+ peaks suggests multiple sources
                    confidence = min(0.85, 0.55 + peaks * 0.05)
                    timestamp_sec = start / sr
                    violations.append({
                        "type": "multiple_voices_detected",
                        "confidence": round(confidence, 3),
                        "start_time": self._fmt(timestamp_sec),
                        "end_time": self._fmt(timestamp_sec + 2),
                        "duration": "2.0s",
                        "duration_seconds": 2.0,
                        "screenshot": "N/A",
                        "description": f"Multiple voice sources detected at {self._fmt(timestamp_sec)} (peaks={peaks})",
                    })

        return self._merge_audio_violations(violations)

    def _detect_sudden_noise(self) -> List[dict]:
        """Detect sudden noise bursts (e.g., someone talking nearby, phone ring)."""
        violations = []
        if self._audio_data is None:
            return violations

        sr = self._sample_rate
        window = sr // 4  # 250ms windows

        # Compute rolling RMS
        rms_values = []
        for i in range(0, len(self._audio_data) - window, window):
            chunk = self._audio_data[i:i + window]
            rms_values.append(np.sqrt(np.mean(chunk**2)))

        if len(rms_values) < 3:
            return violations

        rms_arr = np.array(rms_values)
        baseline = np.percentile(rms_arr, 25)  # Quiet baseline

        # Find sudden jumps (3x the baseline)
        spike_threshold = max(baseline * 3.0, 0.05)
        spikes = np.where(rms_arr > spike_threshold)[0]

        if len(spikes) == 0:
            return violations

        # Group consecutive spikes
        groups = []
        start = spikes[0]
        end = spikes[0]
        for s in spikes[1:]:
            if s - end <= 4:  # Within 1s (4 x 250ms)
                end = s
            else:
                groups.append((start, end))
                start = s; end = s
        groups.append((start, end))

        for s, e in groups:
            t_start = s * 0.25
            t_end = (e + 1) * 0.25
            duration = t_end - t_start
            if duration < 0.5:
                continue
            confidence = min(0.88, 0.60 + rms_arr[s:e+1].max() / (baseline + 1e-6) * 0.05)
            violations.append({
                "type": "audio_anomaly",
                "confidence": round(confidence, 3),
                "start_time": self._fmt(t_start),
                "end_time": self._fmt(t_end),
                "duration": f"{duration:.1f}s",
                "duration_seconds": round(duration, 2),
                "screenshot": "N/A",
                "description": f"Sudden noise burst detected ({duration:.1f}s)",
            })

        return violations

    def _detect_suspicious_silence(self) -> List[dict]:
        """
        Detect unusually long silence periods (possible screen-share audio muting).
        """
        violations = []
        if self._audio_data is None:
            return violations

        sr = self._sample_rate
        silence_threshold = self.config.get("silence_threshold_sec", 30.0)
        window = sr  # 1s windows
        rms_values = []
        for i in range(0, len(self._audio_data), window):
            chunk = self._audio_data[i:i + window]
            rms_values.append(np.sqrt(np.mean(chunk**2)))

        silent_start = None
        for i, rms in enumerate(rms_values):
            if rms < 0.005:
                if silent_start is None:
                    silent_start = i
                elif (i - silent_start) >= silence_threshold:
                    duration = (i - silent_start)
                    violations.append({
                        "type": "suspicious_silence",
                        "confidence": 0.70,
                        "start_time": self._fmt(float(silent_start)),
                        "end_time": self._fmt(float(i)),
                        "duration": f"{duration:.1f}s",
                        "duration_seconds": float(duration),
                        "screenshot": "N/A",
                        "description": f"Prolonged silence: {duration:.0f}s (possible audio muting)",
                    })
                    silent_start = None
            else:
                silent_start = None

        return violations

    @staticmethod
    def _merge_audio_violations(violations: List[dict], gap_sec: float = 5.0) -> List[dict]:
        """Merge consecutive similar violations."""
        if not violations:
            return []
        merged = [violations[0]]
        for v in violations[1:]:
            last = merged[-1]
            if v["type"] == last["type"]:
                try:
                    last_end = sum(int(x)*[3600,60,1][i] for i,x in enumerate(last["end_time"].split(":")))
                    curr_start = sum(int(x)*[3600,60,1][i] for i,x in enumerate(v["start_time"].split(":")))
                    if curr_start - last_end <= gap_sec:
                        # Extend
                        merged[-1]["end_time"] = v["end_time"]
                        continue
                except Exception:
                    pass
            merged.append(v)
        return merged

    @staticmethod
    def _fmt(seconds: float) -> str:
        s = int(seconds)
        return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
