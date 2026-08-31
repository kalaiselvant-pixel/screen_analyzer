#!/usr/bin/env python3
"""
Screen Analyzer CLI
Usage:
    python main.py <video_path> [options]
"""

import argparse
import sys
import json
import time
import os
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Screen Analyzer for Double Proctoring - Overlay & Anomaly Detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py interview.mp4
  python main.py interview.mp4 report.pdf
  python main.py interview.mp4 report.pdf --mode webcam
  python main.py interview.mp4 --output results/ --fps 3 --threshold 0.6
  python main.py interview.mp4 --no-annotate --quiet
        """
    )
    parser.add_argument("video", help="Path to video file (.mp4, .avi, .mov, .mkv)")
    parser.add_argument("pdf", nargs="?", help="Destination PDF path (default: <output>/report.pdf)")
    parser.add_argument("--output", "-o", default="output", help="Output directory (default: output/)")
    parser.add_argument("--mode", choices=("screen", "webcam", "full"), default="full",
                        help="Analysis mode: direct screen only, webcam only, or full pipeline (default: full)")
    parser.add_argument("--fps", "-f", type=float, default=2.0,
                        help="Frames per second to analyze (default: 2)")
    parser.add_argument("--threshold", "-t", type=float, default=0.55,
                        help="Confidence threshold 0-1 (default: 0.55)")
    parser.add_argument("--change-threshold", type=float, default=0.30,
                        help="Screen change sensitivity 0-1 (default: 0.30)")
    parser.add_argument("--no-annotate", action="store_true",
                        help="Skip drawing bounding boxes on screenshots")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress progress output")
    parser.add_argument("--json-only", action="store_true",
                        help="Print only the JSON report to stdout")
    return parser.parse_args()


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════╗
║     🔒 Screen Analyzer for Double Proctoring v1.0       ║
║     Overlay & Anomaly Detection System                   ║
╚══════════════════════════════════════════════════════════╝
""")


def print_progress(progress: float, status: str, quiet: bool):
    if quiet:
        return
    bar_len = 40
    filled = int(bar_len * progress)
    bar = "█" * filled + "░" * (bar_len - filled)
    pct = int(progress * 100)
    print(f"\r  [{bar}] {pct:3d}%  {status:<45}", end="", flush=True)
    if progress >= 1.0:
        print()


def main():
    args = parse_args()

    if not args.json_only:
        print_banner()

    # Validate video
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"❌ Error: Video file not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    supported = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv"}
    if video_path.suffix.lower() not in supported:
        print(f"⚠️  Warning: Unsupported extension '{video_path.suffix}'. Attempting anyway.")

    config = {
        "output_dir": args.output,
        "pdf_path": args.pdf,
        "mode": args.mode,
        "frame_sample_rate": args.fps,
        "model_name": "yolov8n.pt",
        "overlay_confidence_threshold": args.threshold,
        "change_threshold": args.change_threshold,
        "save_annotated_frames": True,
        "draw_bounding_boxes": not args.no_annotate,
        "min_incident_duration": 0.5,
        "popup_area_ratio": 0.05,
        "resize_width": 1280,
    }

    if not args.json_only:
        print(f"  📹 Video   : {video_path}")
        print(f"  📁 Output  : {args.output}/")
        print(f"  🧭 Mode    : {args.mode}")
        print(f"  ⚡ FPS     : {args.fps} frames/sec analyzed")
        print(f"  🎯 Threshold: {args.threshold}")
        print()

    from analyzer import ScreenAnalyzer

    analyzer = ScreenAnalyzer(config)
    quiet = args.quiet or args.json_only

    def cb(progress, status):
        print_progress(progress, status, quiet)

    if not quiet:
        print("  Analyzing video...")

    start = time.time()
    result = analyzer.analyze(str(video_path), progress_callback=cb)
    elapsed = time.time() - start

    if args.json_only:
        print(json.dumps(result, indent=2))
        return

    print()

    if result["status"] == "error":
        print(f"\n❌ Analysis failed: {result['message']}")
        sys.exit(1)

    # Print results
    violations = result["violations"]
    risk = result["risk_level"]
    risk_icon = {"CLEAN": "✅", "LOW": "🟡", "MEDIUM": "🟠", "HIGH": "🔴"}.get(risk, "⚠️")

    print(f"\n{'─'*60}")
    print(f"  {risk_icon}  Risk Level    : {risk}")
    print(f"  📊 Violations   : {len(violations)}")
    print(f"  🎞️  Frames       : {result['frames_analyzed']}")
    print(f"  ⏱️  Duration     : {result['video_duration']}")
    print(f"  ⚙️  Processed in : {elapsed:.1f}s")
    print(f"{'─'*60}")

    if violations:
        print(f"\n  Detected Violations:\n")
        for i, v in enumerate(violations, 1):
            ss = os.path.basename(v['screenshot']) if v['screenshot'] != 'N/A' else 'N/A'
            print(f"  [{i:02d}] {v['type'].upper()}")
            print(f"       Start     : {v['start_time']}")
            print(f"       End       : {v['end_time']}")
            print(f"       Duration  : {v['duration']}")
            print(f"       Confidence: {v['confidence']:.0%}")
            print(f"       Screenshot: {ss}")
            if v.get('description'):
                print(f"       Info      : {v['description']}")
            print()
    else:
        print("\n  ✅ No violations detected. Session appears clean.\n")

    print(f"  📄 JSON report : {result.get('report_json', 'output/report.json')}")
    print(f"  🌐 HTML report : {result.get('report_html', 'output/report.html')}")
    print(f"  🖼️  Screenshots : {args.output}/screenshots/\n")


if __name__ == "__main__":
    main()
