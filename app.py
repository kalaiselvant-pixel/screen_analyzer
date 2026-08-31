from pathlib import Path

import streamlit as st

from analyzer import ScreenAnalyzer
from utils.ui_helpers import build_run_paths, ensure_runtime_dirs


APP_TITLE = "Screen Analyzer"
SAMPLE_VIDEO_PATH = Path("interview.mp4")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg-a: #f5f1e8;
            --bg-b: #f7fbff;
            --ink: #152235;
            --muted: #5b6878;
            --card: rgba(255, 255, 255, 0.72);
            --line: rgba(21, 34, 53, 0.08);
            --brand: #ff6b2c;
            --brand-2: #f0b429;
            --accent: #0f6cbd;
            --good: #0f766e;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(255, 107, 44, 0.18), transparent 24%),
                radial-gradient(circle at top right, rgba(15, 108, 189, 0.16), transparent 26%),
                linear-gradient(180deg, var(--bg-a) 0%, var(--bg-b) 100%);
            color: var(--ink);
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        [data-testid="stToolbar"] {
            display: none;
        }

        #MainMenu {
            visibility: hidden;
        }

        [data-testid="stAppViewContainer"] > .main {
            animation: page-rise 0.7s ease-out;
        }

        @keyframes page-rise {
            from { opacity: 0; transform: translateY(18px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .hero-shell {
            position: relative;
            overflow: hidden;
            padding: 2.3rem 2.2rem;
            border-radius: 28px;
            background: linear-gradient(145deg, rgba(255,255,255,0.84), rgba(255,255,255,0.56));
            border: 1px solid rgba(255,255,255,0.65);
            box-shadow: 0 22px 60px rgba(24, 39, 75, 0.12);
            backdrop-filter: blur(16px);
            margin-bottom: 1.5rem;
        }

        .hero-shell::after {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(120deg, transparent 0%, rgba(255,255,255,0.35) 30%, transparent 55%);
            transform: translateX(-120%);
            animation: shimmer 6s linear infinite;
        }

        @keyframes shimmer {
            to { transform: translateX(120%); }
        }

        .hero-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.45rem 0.9rem;
            border-radius: 999px;
            background: rgba(15, 108, 189, 0.1);
            color: var(--accent);
            font-size: 0.85rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }

        .hero-title {
            margin: 1rem 0 0.6rem 0;
            font-size: 3rem;
            line-height: 1.02;
            font-weight: 800;
            letter-spacing: -0.04em;
            color: var(--ink);
        }

        .hero-copy {
            max-width: 44rem;
            margin: 0;
            font-size: 1.05rem;
            line-height: 1.7;
            color: var(--muted);
        }

        .hero-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.9rem;
            margin-top: 1.6rem;
        }

        .hero-stat,
        .glass-card,
        .metric-card,
        .upload-preview {
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: 22px;
            box-shadow: 0 14px 30px rgba(24, 39, 75, 0.08);
            backdrop-filter: blur(10px);
        }

        .hero-stat {
            padding: 1rem 1.1rem;
            animation: float-in 0.75s ease-out;
        }

        @keyframes float-in {
            from { opacity: 0; transform: translateY(14px) scale(0.98); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }

        .hero-stat b,
        .metric-card b {
            display: block;
            color: var(--ink);
            font-size: 1.15rem;
            margin-bottom: 0.25rem;
        }

        .hero-stat span,
        .metric-card span {
            color: var(--muted);
            font-size: 0.93rem;
        }

        .glass-card {
            padding: 1.25rem 1.25rem 1rem 1.25rem;
            margin-top: 0.6rem;
        }

        .upload-zone {
            margin-top: 1rem;
            margin-bottom: 2.4rem;
        }

        .upload-zone [data-testid="stFileUploader"] {
            max-width: 780px;
            margin: 0 auto;
        }

        .upload-zone [data-testid="stFileUploaderDropzone"] {
            min-height: 260px;
            border-radius: 26px;
            border: 1.5px dashed rgba(15, 108, 189, 0.35);
            background:
                radial-gradient(circle at top left, rgba(255, 107, 44, 0.08), transparent 26%),
                linear-gradient(145deg, rgba(255,255,255,0.92), rgba(247,251,255,0.86));
            box-shadow: 0 18px 40px rgba(24, 39, 75, 0.08);
            padding: 1.3rem;
            transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
        }

        .upload-zone [data-testid="stFileUploaderDropzone"]:hover {
            transform: translateY(-2px);
            border-color: rgba(255, 107, 44, 0.55);
            box-shadow: 0 24px 48px rgba(24, 39, 75, 0.12);
        }

        .upload-zone section {
            gap: 0.9rem;
        }

        .upload-zone small {
            font-size: 0.95rem;
            color: var(--muted);
        }

        .upload-zone button[kind="secondary"] {
            border-radius: 14px;
            border: 1px solid rgba(21, 34, 53, 0.14);
            min-height: 48px;
            padding: 0.55rem 1.1rem;
            font-weight: 700;
        }

        .upload-zone [data-testid="stFileUploaderDropzoneInstructions"] div {
            font-size: 1.05rem;
            color: var(--ink);
            font-weight: 600;
        }

        .upload-lead {
            max-width: 780px;
            margin: 0 auto 0.85rem auto;
            text-align: center;
            color: var(--muted);
            font-size: 0.98rem;
            line-height: 1.6;
        }

        .controls-panel {
            padding-top: 0.35rem;
        }

        .section-kicker {
            margin: 0;
            color: var(--accent);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.8rem;
        }

        .section-title {
            margin: 0.25rem 0 0.4rem 0;
            color: var(--ink);
            font-size: 1.5rem;
            font-weight: 800;
            letter-spacing: -0.02em;
        }

        .section-copy {
            margin: 0;
            color: var(--muted);
            line-height: 1.65;
        }

        .metric-wrap {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.9rem;
            margin: 0.8rem 0 1rem 0;
        }

        .metric-card {
            padding: 1rem 1.1rem;
        }

        .incident-card {
            padding: 1rem 1rem 0.25rem 1rem;
            margin-bottom: 0.8rem;
            border-radius: 18px;
            border: 1px solid var(--line);
            background: rgba(255,255,255,0.74);
        }

        .upload-preview {
            position: relative;
            overflow: hidden;
            padding: 1rem 1rem 0.6rem 1rem;
            margin-top: 1rem;
            animation: float-in 0.7s ease-out;
        }

        .upload-preview::before {
            content: "";
            position: absolute;
            inset: -1px;
            border-radius: 22px;
            padding: 1px;
            background: linear-gradient(135deg, rgba(255,107,44,0.9), rgba(15,108,189,0.75), rgba(240,180,41,0.9));
            -webkit-mask:
                linear-gradient(#fff 0 0) content-box,
                linear-gradient(#fff 0 0);
            -webkit-mask-composite: xor;
            mask-composite: exclude;
            animation: border-glow 3.2s linear infinite;
        }

        @keyframes border-glow {
            0% { filter: hue-rotate(0deg); opacity: 0.9; }
            50% { filter: hue-rotate(25deg); opacity: 1; }
            100% { filter: hue-rotate(0deg); opacity: 0.9; }
        }

        .upload-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.45rem 0.8rem;
            margin-bottom: 0.7rem;
            border-radius: 999px;
            background: rgba(15, 118, 110, 0.12);
            color: var(--good);
            font-weight: 700;
            font-size: 0.9rem;
        }

        .upload-meta {
            color: var(--muted);
            font-size: 0.94rem;
            margin-bottom: 0.8rem;
        }

        .download-card {
            padding: 1.1rem 1.2rem;
            border-left: 5px solid var(--brand);
        }

        .download-frame {
            margin-top: 0.8rem;
            padding: 1.15rem 1.2rem 1rem 1.2rem;
            border-radius: 22px;
            border-left: 5px solid var(--brand);
            background: var(--card);
            border-top: 1px solid var(--line);
            border-right: 1px solid var(--line);
            border-bottom: 1px solid var(--line);
            box-shadow: 0 14px 30px rgba(24, 39, 75, 0.08);
        }

        .download-frame h3 {
            margin: 0 0 0.3rem 0;
            color: var(--ink);
            font-size: 1.15rem;
        }

        .download-frame p {
            margin: 0 0 0.9rem 0;
            color: var(--muted);
        }

        .sample-card {
            margin-top: 1rem;
            padding: 1rem 1.1rem;
        }

        .sample-card p {
            margin: 0;
            color: var(--muted);
            line-height: 1.6;
        }

        .soft-note {
            color: var(--muted);
            font-size: 0.92rem;
            margin: 1.6rem 0 1.8rem 0;
        }

        .risk-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.45rem 0.8rem;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.92rem;
        }

        .risk-high { background: rgba(187, 37, 37, 0.1); color: #9f1239; }
        .risk-medium { background: rgba(240, 180, 41, 0.18); color: #92400e; }
        .risk-low { background: rgba(15, 118, 110, 0.12); color: #115e59; }
        .risk-clean { background: rgba(15, 118, 110, 0.12); color: #115e59; }

        @media (max-width: 900px) {
            .hero-title { font-size: 2.2rem; }
            .hero-grid, .metric-wrap { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <section class="hero-shell">
            <div class="hero-badge">Local report workflow</div>
            <h1 class="hero-title">Screen Analyzer</h1>
            <p class="hero-copy">
                Upload one video and generate a polished PDF report with incident summaries, timestamps,
                and evidence screenshots in one smooth flow.
            </p>
            <div class="hero-grid">
                <div class="hero-stat"><b>One-file input</b><span>Upload only the video and start analysis.</span></div>
                <div class="hero-stat"><b>Evidence-rich PDF</b><span>Get screenshots, timing, and risk summary in one file.</span></div>
                <div class="hero-stat"><b>Local-first</b><span>Files stay in this workspace for review and download.</span></div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_summary(result: dict, pdf_path: Path) -> None:
    risk = (result.get("risk_level") or "UNKNOWN").lower()
    risk_class = {
        "high": "risk-high",
        "medium": "risk-medium",
        "low": "risk-low",
        "clean": "risk-clean",
    }.get(risk, "risk-low")
    risk_label = result.get("risk_level", "UNKNOWN")

    st.markdown(
        f"""
        <div class="glass-card">
            <p class="section-kicker">Report ready</p>
            <h2 class="section-title">Analysis summary</h2>
            <p class="section-copy">
                <span class="risk-pill {risk_class}">Risk level: {risk_label}</span>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    total = result.get("total_violations", len(result.get("violations", [])))
    frames = result.get("frames_analyzed", 0)
    duration = result.get("video_duration", "N/A")
    mode = str(result.get("mode", "full")).title()

    st.markdown(
        f"""
        <div class="metric-wrap">
            <div class="metric-card"><b>{total}</b><span>Total incidents</span></div>
            <div class="metric-card"><b>{frames}</b><span>Frames analyzed</span></div>
            <div class="metric-card"><b>{duration}</b><span>Video duration</span></div>
            <div class="metric-card"><b>{mode}</b><span>Analysis mode</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    pdf_bytes = pdf_path.read_bytes()
    st.markdown(
        """
        <div class="download-frame">
            <h3>Download report</h3>
            <p>Your PDF is ready. Download it here or use the saved local file path below.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.download_button(
        "Download PDF report",
        data=pdf_bytes,
        file_name=pdf_path.name,
        mime="application/pdf",
        use_container_width=True,
        key=f"download_pdf_{pdf_path.name}",
    )
    st.caption(f"Saved locally at: {pdf_path.resolve()}")


def render_sample_download() -> None:
    if not SAMPLE_VIDEO_PATH.exists():
        return

    st.markdown(
        """
        <div class="glass-card sample-card">
            <p><strong>Need a sample file?</strong> Download the bundled offline demo video and try the full report flow right away.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.download_button(
        "Download sample video",
        data=SAMPLE_VIDEO_PATH.read_bytes(),
        file_name=SAMPLE_VIDEO_PATH.name,
        mime="video/mp4",
        use_container_width=True,
        key="download_sample_video",
    )


def render_violations(result: dict) -> None:
    violations = result.get("violations", [])
    if not violations:
        st.success("No violations were recorded for this run.")
        return

    st.markdown(
        """
        <div class="glass-card">
            <p class="section-kicker">Evidence</p>
            <h2 class="section-title">Incident review</h2>
            <p class="section-copy">Each card shows the captured screenshot, timing, and model confidence for that incident.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for index, violation in enumerate(violations, start=1):
        st.markdown('<div class="incident-card">', unsafe_allow_html=True)
        title = f"#{index} {violation['type']} ({violation['start_time']} -> {violation['end_time']})"
        with st.expander(title, expanded=index <= 2):
            left, right = st.columns([1.05, 1.6], gap="large")
            with left:
                st.write(f"Start: `{violation['start_time']}`")
                st.write(f"End: `{violation['end_time']}`")
                st.write(f"Duration: `{violation['duration']}`")
                st.write(f"Frames flagged: `{violation.get('frames_flagged', 'N/A')}`")
                st.write(f"Avg confidence: `{violation.get('avg_confidence', violation.get('confidence', 0)):.2f}`")
                if violation.get("description"):
                    st.write(f"Details: {violation['description']}")
            with right:
                screenshot = violation.get("screenshot")
                if screenshot and screenshot != "N/A":
                    screen_path = Path(screenshot)
                    if not screen_path.is_absolute():
                        screen_path = Path.cwd() / screen_path
                    if screen_path.exists():
                        st.image(str(screen_path), use_container_width=True)
                    else:
                        st.info("Screenshot path was recorded, but the file is not available.")
                else:
                    st.info("No screenshot was captured for this incident.")
        st.markdown("</div>", unsafe_allow_html=True)


def render_uploaded_video(uploaded_file) -> None:
    size_mb = uploaded_file.size / (1024 * 1024)
    suffix = Path(uploaded_file.name).suffix.lower() or ".mp4"
    mime = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
        ".flv": "video/x-flv",
    }.get(suffix, "video/mp4")

    st.markdown(
        f"""
        <div class="upload-preview">
            <div class="upload-chip">Video loaded</div>
            <div class="upload-meta">
                <strong>{uploaded_file.name}</strong> · {size_mb:.2f} MB
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.video(uploaded_file.getvalue(), format=mime)


def run_analysis(uploaded_file, mode: str, fps: float, threshold: float) -> tuple[dict, Path]:
    ensure_runtime_dirs()
    paths = build_run_paths(uploaded_file.name)
    paths["run_dir"].mkdir(parents=True, exist_ok=True)
    paths["upload_path"].write_bytes(uploaded_file.getbuffer())

    progress = st.progress(0, text="Preparing analysis")
    status = st.empty()

    def progress_callback(value: float, label: str) -> None:
        pct = max(0, min(int(value * 100), 100))
        progress.progress(pct, text=label)
        status.caption(label)

    config = {
        "output_dir": str(paths["run_dir"]),
        "pdf_path": str(paths["pdf_path"]),
        "mode": mode,
        "frame_sample_rate": fps,
        "model_name": "yolov8n.pt",
        "overlay_confidence_threshold": threshold,
        "change_threshold": 0.30,
        "save_annotated_frames": True,
        "draw_bounding_boxes": True,
        "min_incident_duration": 0.5,
        "popup_area_ratio": 0.05,
        "resize_width": 1280,
    }

    analyzer = ScreenAnalyzer(config)
    result = analyzer.analyze(str(paths["upload_path"]), progress_callback=progress_callback)

    progress.progress(100, text="Analysis complete")
    status.caption("PDF generated and ready to download.")
    return result, paths["pdf_path"]


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="📄",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_styles()
    render_hero()

    st.markdown(
        """
        <div class="glass-card">
            <p class="section-kicker">Start here</p>
            <h2 class="section-title">Upload a recording</h2>
            <p class="section-copy">Use webcam mode for room-camera interview videos and full mode only when the input really contains desktop-screen evidence.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    controls_col, info_col = st.columns([1.25, 0.75], gap="large")
    with controls_col:
        st.markdown(
            """
            <div class="upload-lead">
                Drag and drop your interview recording here, or browse to choose a file.
                The app will keep the uploaded video in the local workspace and generate a downloadable PDF report.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="upload-zone">', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "Interview video",
            type=["mp4", "avi", "mov", "mkv", "webm", "flv"],
            help="Upload a recorded interview or proctoring session video.",
        )
        st.markdown("</div>", unsafe_allow_html=True)
    with info_col:
        st.markdown('<div class="controls-panel">', unsafe_allow_html=True)
        mode = st.selectbox(
            "Analysis mode",
            options=["webcam", "full", "screen"],
            index=0,
            help="Webcam mode is recommended for room-camera videos like your current sample.",
        )
        fps = st.slider("Frames analyzed per second", min_value=0.5, max_value=5.0, value=2.0, step=0.5)
        threshold = st.slider("Confidence threshold", min_value=0.30, max_value=0.95, value=0.55, step=0.05)
        render_sample_download()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        <p class="soft-note">
            The generated files are saved under <code>output/ui_reports/</code>, and the app shows a direct PDF download button after analysis.
        </p>
        """,
        unsafe_allow_html=True,
    )

    if uploaded_file:
        render_uploaded_video(uploaded_file)

    generate = st.button("Generate report", type="primary", use_container_width=True)

    if generate and not uploaded_file:
        st.warning("Upload a video file first.")
        return

    if generate and uploaded_file:
        with st.spinner("Running analysis and building the PDF report..."):
            result, pdf_path = run_analysis(uploaded_file, mode, fps, threshold)

        if result.get("status") == "error":
            st.error(result.get("message", "Analysis failed."))
            return

        render_summary(result, pdf_path)
        render_violations(result)


if __name__ == "__main__":
    main()
