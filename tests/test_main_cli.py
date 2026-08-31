import sys

from main import parse_args


def test_parse_args_defaults_to_full_mode(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "interview.mp4"])
    args = parse_args()

    assert args.mode == "full"


def test_parse_args_accepts_webcam_mode(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "interview.mp4", "report.pdf", "--mode", "webcam"])
    args = parse_args()

    assert args.pdf == "report.pdf"
    assert args.mode == "webcam"
