# 🔒 Screen Analyzer for Double Proctoring

> **Overlay & Anomaly Detection System** — detects unauthorized windows, screen switches, popups, and AI tool usage during recorded interview sessions.

---

## 📌 Features

| Capability | Method |
|---|---|
| Multiple window / overlay detection | Contour analysis + diff-based segmentation |
| Screen switching detection | SSIM + histogram comparison |
| Popup / dialog detection | Region brightness + contour analysis |
| Browser tab bar detection | Edge density + vertical separator counting |
| Chat sidebar detection | Horizontal line pattern + region diff |
| Confidence scoring | Per-detector weighted signal fusion |
| Incident merging | Temporal gap-based grouping |
| JSON report | Machine-readable violation log |
| HTML report | Human-readable with screenshots |
| Annotated screenshots | Bounding boxes + labels per violation |

---

## 🚀 Quick Start

### Install dependencies
```bash
pip install -r requirements.txt
```

### Analyze a video
```bash
python main.py interview.mp4
```

### Launch the local upload UI
```bash
streamlit run app.py
```

### Launch the UI and open it in the browser
```powershell
.\launch_ui.ps1
```

### Options
```bash
python main.py interview.mp4 \
  --output results/          \   # Output directory
  --fps 3                    \   # Frames per second to analyze
  --threshold 0.6            \   # Confidence threshold (0–1)
  --change-threshold 0.25    \   # Screen switch sensitivity
  --no-annotate              \   # Skip bounding box drawing
  --quiet                    \   # Suppress progress output
  --json-only                    # Print JSON to stdout only
```

---

## 📁 Project Structure

```
screen_analyzer/
├── main.py                   # CLI entry point
├── analyzer.py               # Core orchestration pipeline
├── requirements.txt
├── models/
│   ├── overlay_detector.py   # Rectangular overlay & popup detection
│   ├── screen_change_detector.py  # Screen switch via SSIM
│   └── ui_element_detector.py     # Taskbar, browser chrome, sidebars
├── utils/
│   ├── frame_processor.py    # Preprocessing (resize, denoise)
│   ├── incident_tracker.py   # Temporal grouping of detections
│   └── report_generator.py   # JSON + HTML report generation
├── tests/
│   └── test_analyzer.py      # Full test suite (31 tests, all AC)
└── output/                   # Generated at runtime
    ├── report.json
    ├── report.html
    └── screenshots/
```

---

## 📊 Sample Output

### JSON Report (`output/report.json`)
```json
{
  "status": "success",
  "generated_at": "2025-08-15T14:32:01",
  "video_file": "interview.mp4",
  "video_duration": "312.4s",
  "frames_analyzed": 624,
  "processing_time": "48.3s",
  "total_violations": 3,
  "risk_level": "MEDIUM",
  "violation_summary": {
    "overlay_detected": 2,
    "screen_switch": 1
  },
  "violations": [
    {
      "start_time": "00:01:23",
      "end_time": "00:01:40",
      "duration": "17.0s",
      "duration_seconds": 17.0,
      "type": "overlay_detected",
      "confidence": 0.82,
      "screenshot": "output/screenshots/frame_000830_overlay_detected_00-01-23.png",
      "description": "Rectangular overlay covering 42.3% of screen"
    },
    {
      "start_time": "00:03:11",
      "end_time": "00:03:11",
      "duration": "0.5s",
      "type": "screen_switch",
      "confidence": 0.91,
      "screenshot": "output/screenshots/frame_001910_screen_switch_00-03-11.png",
      "description": "Abrupt screen switch detected (change=58.2%)"
    }
  ]
}
```

---

## 🎯 Detection Methods

### 1. Overlay Detection (`OverlayDetector`)
- **Rectangular overlay**: Compares current vs baseline frame using absolute difference, then finds large structured changed regions via morphological analysis.
- **Window border detection**: Uses Canny edge detection + polygon approximation to find 4-sided shapes with title-bar-like structure.
- **Popup detection**: Looks for small-to-medium rectangular brightness changes in corner regions.

### 2. Screen Switch Detection (`ScreenChangeDetector`)
- Computes **SSIM** (Structural Similarity Index) between consecutive frames.
- Cross-validates with **histogram Bhattacharyya distance**.
- Uses a 5-frame rolling average to suppress transient glitches.
- Includes 2-second debounce to avoid duplicate events.

### 3. UI Element Detection (`UIElementDetector`)
- **Taskbar regions**: Checks top/bottom 60px bands for edge density + diff.
- **Notification popups**: Scans corners for bright rectangular regions.
- **Browser chrome**: Detects horizontal bands + tab separator counts.
- **Chat sidebars**: Identifies edge-dense vertical panels on screen edges.

### Confidence Scoring
Each detector returns a `confidence` value in `[0.0, 1.0]`:
- Signals are linearly combined from multiple independent measurements.
- Detections below `--threshold` (default 0.55) are discarded.
- Only the strongest screenshot per merged incident is kept.

---

## 🔄 Processing Pipeline

```
Video File
    │
    ▼
Frame Sampling (every N frames based on --fps)
    │
    ▼
Frame Preprocessing (resize → bilateral filter)
    │
    ▼
┌───────────────────────────────────────┐
│  3 Parallel Detectors                 │
│  1. OverlayDetector                   │
│  2. ScreenChangeDetector              │
│  3. UIElementDetector                 │
└──────────────────┬────────────────────┘
                   │
                   ▼
           IncidentTracker
      (groups consecutive hits,
       merges within 3s gap,
       filters < 0.5s)
                   │
                   ▼
         Screenshot + Annotation
                   │
                   ▼
        JSON Report + HTML Report
```

---

## 🧪 Running Tests

```bash
# With pytest (if available):
pytest tests/ -v

# With Python directly:
python -m unittest discover tests/
```

All **31 tests** cover every Acceptance Criterion:
- **AC1** — Video input processing (3 tests)
- **AC2** — Overlay/anomaly detection (5 tests)
- **AC3** — AI/model-based approach (3 tests)
- **AC4** — Incident reporting with timestamps (9 tests)
- **AC5** — Output & performance (9 tests)

---

## ⚙️ Configuration Reference

| Key | Default | Description |
|---|---|---|
| `frame_sample_rate` | `2` | Frames per second to analyze |
| `overlay_confidence_threshold` | `0.55` | Minimum confidence to record |
| `change_threshold` | `0.30` | SSIM change to trigger screen switch |
| `min_incident_duration` | `0.5` | Minimum seconds for a valid incident |
| `popup_area_ratio` | `0.05` | Minimum area ratio for popup |
| `resize_width` | `1280` | Max width for processing (performance) |
| `draw_bounding_boxes` | `True` | Annotate screenshots |

---

## 📦 Dependencies

| Package | Version | Purpose |
|---|---|---|
| `opencv-python` | ≥ 4.8 | Video I/O, image processing |
| `numpy` | ≥ 1.24 | Array operations |
| `scikit-image` | ≥ 0.21 | SSIM computation |
| `pytest` | ≥ 7.4 | Test runner |

---

## 🏗️ Extending the System

### Add a custom detector
```python
class MyDetector:
    def __init__(self, config): ...
    def detect(self, frame, baseline) -> List[dict]:
        # Return list of: {"type": str, "confidence": float, "bbox": tuple, "description": str}
        return []
```

Then register it in `analyzer.py`:
```python
self.my_detector = MyDetector(self.config)
# In _run_detections():
detections.extend(self.my_detector.detect(frame, baseline))
```

### Use as a Python library
```python
from analyzer import ScreenAnalyzer

sa = ScreenAnalyzer({
    "output_dir": "my_results",
    "overlay_confidence_threshold": 0.6,
})

result = sa.analyze("candidate_session.mp4")
print(f"Risk: {result['risk_level']}")
for v in result["violations"]:
    print(f"[{v['start_time']}] {v['type']} ({v['confidence']:.0%})")
```

---

## 📄 License
MIT — Free for commercial and academic use.
