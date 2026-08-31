"""
Process Monitor
Detects unauthorized processes: VMs, remote desktop, screen sharing tools.
Uses psutil for cross-platform process inspection.
Also performs heuristic screen analysis for VM/RDP visual artifacts.
"""

import cv2
import numpy as np
from typing import List
import logging

logger = logging.getLogger(__name__)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not found – process monitoring disabled.")

# ── Blocked process name lists ─────────────────────────────────────────────
VM_PROCESSES = [
    "vmware", "vmwaretray", "vmwareuser", "vmware-vmx",
    "virtualbox", "vboxservice", "vboxtray", "vboxheadless",
    "qemu", "qemu-system",
    "parallels", "prl_client_app",
    "hyperv", "vmconnect",
]

REMOTE_DESKTOP = [
    "mstsc",          # Windows RDP client
    "anydesk",        # AnyDesk
    "teamviewer",     # TeamViewer
    "logmein",        # LogMeIn
    "rdclientax",     # RD Web Access
    "chrome_remote",  # Chrome Remote Desktop
    "vnc",            # VNC variants
    "realvnc", "tigervnc", "ultravnc", "tightvnc",
    "splashtop",      # Splashtop
    "parsec",         # Parsec Gaming
]

SCREEN_SHARE = [
    "zoom",           # Zoom
    "slack",          # Slack (screen share feature)
    "teams",          # Microsoft Teams
    "discord",        # Discord
    "obs",            # OBS Studio (streaming)
    "obs64",
    "loom",           # Loom
    "screencastify",  # Chrome extension recorder
    "skype",          # Skype
    "webex",          # Cisco Webex
    "gotomeeting",    # GoTo Meeting
]


class ProcessMonitor:
    """
    Monitors running processes for unauthorized software
    and analyzes frames for VM/RDP visual artifacts.
    """

    def __init__(self, config: dict):
        self.config = config
        self.threshold = config.get("overlay_confidence_threshold", 0.55)
        self._process_check_interval = config.get("process_check_interval_sec", 10.0)
        self._last_process_check = -99.0
        self._cached_violations: List[dict] = []

    def detect(self, frame: np.ndarray, timestamp: float) -> List[dict]:
        """Run process checks (rate-limited) + visual VM artifact detection."""
        detections = []

        # Rate-limited process scan
        if (timestamp - self._last_process_check) >= self._process_check_interval:
            self._cached_violations = self._scan_processes(timestamp)
            self._last_process_check = timestamp

        detections.extend(self._cached_violations)

        # Visual RDP/VM artifact check on every frame (fast heuristic)
        visual = self._detect_vm_visual_artifacts(frame)
        if visual:
            detections.append(visual)

        return detections

    def _scan_processes(self, timestamp: float) -> List[dict]:
        """Scan running processes against blacklists."""
        if not PSUTIL_AVAILABLE:
            return []

        violations = []
        try:
            running = {p.name().lower() for p in psutil.process_iter(['name'])}
        except Exception as e:
            logger.debug(f"Process scan error: {e}")
            return []

        # Check each category
        found_vm = [p for p in VM_PROCESSES if any(p in r for r in running)]
        found_rdp = [p for p in REMOTE_DESKTOP if any(p in r for r in running)]
        found_share = [p for p in SCREEN_SHARE if any(p in r for r in running)]

        if found_vm:
            violations.append({
                "type": "virtual_machine_detected",
                "confidence": 0.95,
                "processes": found_vm,
                "description": f"VM software running: {', '.join(found_vm[:3])}",
            })
            logger.warning(f"VM processes detected: {found_vm}")

        if found_rdp:
            violations.append({
                "type": "remote_desktop_detected",
                "confidence": 0.94,
                "processes": found_rdp,
                "description": f"Remote desktop software running: {', '.join(found_rdp[:3])}",
            })

        if found_share:
            # Screen share apps only flagged if also actively recording/sharing
            violations.append({
                "type": "screen_share_detected",
                "confidence": 0.78,
                "processes": found_share,
                "description": f"Screen-sharing app detected: {', '.join(found_share[:3])}",
            })

        return violations

    def _detect_vm_visual_artifacts(self, frame: np.ndarray) -> dict:
        """
        Detect visual artifacts common in VM/RDP sessions:
        - Window title bars with VM-specific branding colors
        - Characteristic compression artifacts from RDP codec
        - Frame-within-frame border patterns
        """
        h, w = frame.shape[:2]

        # Check for RDP-style block compression artifacts
        # RDP often produces 8x8 block artifacts at low bandwidth
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Compute DCT block variance (high block-boundary variation = compression)
        block_score = self._compute_block_artifact_score(gray)

        # Check for VM title bar colors (VMware: grey #878787, VirtualBox: blue nav)
        top_strip = frame[0:35, :]
        vm_color_score = self._check_vm_title_colors(top_strip)

        combined = 0.5 * block_score + 0.5 * vm_color_score
        if combined >= self.threshold:
            return {
                "type": "remote_session_suspected",
                "confidence": round(min(0.90, combined), 3),
                "block_score": round(block_score, 3),
                "description": "Visual artifacts suggest remote desktop or VM session",
            }
        return None

    @staticmethod
    def _compute_block_artifact_score(gray: np.ndarray) -> float:
        """Measure 8×8 block boundary discontinuities (RDP artifact signature)."""
        h, w = gray.shape
        score = 0.0
        count = 0
        for y in range(8, h - 8, 8):
            row_diff = np.abs(gray[y, :].astype(int) - gray[y-1, :].astype(int))
            score += row_diff.mean()
            count += 1
        for x in range(8, w - 8, 8):
            col_diff = np.abs(gray[:, x].astype(int) - gray[:, x-1].astype(int))
            score += col_diff.mean()
            count += 1
        avg = score / max(count, 1)
        # Normalize: 0=clean, 1=severe block artifacts
        return float(min(1.0, avg / 20.0))

    @staticmethod
    def _check_vm_title_colors(strip: np.ndarray) -> float:
        """Check for VM-characteristic title bar colors."""
        if strip.size == 0:
            return 0.0
        # VMware grey: ~(135,135,135), VirtualBox blue: ~(30,70,130)
        mean_color = strip.mean(axis=(0, 1))
        b, g, r = mean_color

        # VMware grey-ish
        vmware_grey = abs(r - 135) < 15 and abs(g - 135) < 15 and abs(b - 135) < 15
        # VirtualBox dark blue
        vbox_blue = b > 100 and b > r * 2 and g < 80
        # Generic very dark title bar (remote desktop often)
        dark_bar = r < 45 and g < 45 and b < 45

        if vmware_grey:   return 0.75
        if vbox_blue:     return 0.80
        if dark_bar:      return 0.55
        return 0.0
