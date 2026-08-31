"""
Report Generator — produces JSON + rich HTML report for double proctoring.
"""

import json, os
from pathlib import Path
from datetime import datetime
from html import escape
from typing import Any, Dict, List

VIOLATION_CATEGORIES = {
    # Screen
    "overlay_detected":          ("Screen", "🖥️"),
    "screen_switch":             ("Screen", "🔀"),
    "popup_detected":            ("Screen", "🗯️"),
    "multiple_windows":          ("Screen", "🪟"),
    "ui_anomaly":                ("Screen", "⚠️"),
    "ai_tool_detected":          ("Screen", "🤖"),
    "cheating_site_detected":    ("Screen", "🚫"),
    "solution_content_detected": ("Screen", "📋"),
    "copy_paste_detected":       ("Screen", "📋"),
    "browser_tab_detected":      ("Screen", "🌐"),
    # Process
    "virtual_machine_detected":  ("Process", "💻"),
    "remote_desktop_detected":   ("Process", "🖱️"),
    "screen_share_detected":     ("Process", "📡"),
    "remote_session_suspected":  ("Process", "🔍"),
    # Webcam
    "absence_detected":          ("Webcam", "👤"),
    "multiple_persons":          ("Webcam", "👥"),
    "gaze_away":                 ("Webcam", "👁️"),
    "head_pose_violation":       ("Webcam", "🙄"),
    "phone_detected":            ("Webcam", "📱"),
    # Audio
    "multiple_voices_detected":  ("Audio", "🎤"),
    "audio_anomaly":             ("Audio", "🔊"),
    "suspicious_silence":        ("Audio", "🔇"),
}
VIOLATION_CATEGORIES.update({
    "multiple_people": ("Webcam", "People"),
    "extra_device_detected": ("Screen", "Device"),
})


class ReportGenerator:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def generate(self, violations, video_path, video_duration,
                 frames_analyzed, processing_time,
                 audit_captures=None, mode="full", pdf_path=None,
                 sample_fps=None, model_name=None) -> dict:
        ts = datetime.now().isoformat()
        type_counts = {}
        for v in violations:
            type_counts[v["type"]] = type_counts.get(v["type"], 0) + 1

        # Category summary
        cat_counts = {}
        for vtype, count in type_counts.items():
            cat, _ = VIOLATION_CATEGORIES.get(vtype, ("Other", "⚠️"))
            cat_counts[cat] = cat_counts.get(cat, 0) + count

        report = {
            "status": "success",
            "generated_at": ts,
            "video_file": os.path.basename(video_path),
            "video_duration": f"{video_duration:.1f}s",
            "video_duration_seconds": video_duration,
            "sample_fps": sample_fps,
            "model_name": model_name or "Screen Analyzer detectors",
            "frames_analyzed": frames_analyzed,
            "processing_time": f"{processing_time:.1f}s",
            "mode": mode,
            "total_violations": len(violations),
            "violation_summary": type_counts,
            "category_summary": cat_counts,
            "risk_level": self._risk_level(len(violations), cat_counts),
            "violations": violations,
            "audit_trail": audit_captures or [],
            "output_directory": str(self.output_dir),
        }

        json_path = self.output_dir / "report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

        html_path = self.output_dir / "report.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(self._render_html(report))

        pdf_path = Path(pdf_path) if pdf_path else self.output_dir / "report.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        self._render_pdf(report, pdf_path)

        report["report_json"] = str(json_path)
        report["report_html"] = str(html_path)
        report["report_pdf"] = str(pdf_path)
        return report

    @staticmethod
    def _risk_level(count, cat_counts=None):
        if count == 0: return "CLEAN"
        # High if webcam + screen violations present (true double proctoring catch)
        if cat_counts and len(cat_counts) >= 2 and count >= 3:
            return "HIGH"
        if count <= 2: return "LOW"
        if count <= 5: return "MEDIUM"
        return "HIGH"

    def _render_html(self, r):
        risk = r["risk_level"]
        rc = {"CLEAN":"#22c55e","LOW":"#f59e0b","MEDIUM":"#f97316","HIGH":"#ef4444"}.get(risk,"#6b7280")
        rows = ""
        for i, v in enumerate(r["violations"], 1):
            cat, icon = VIOLATION_CATEGORIES.get(v["type"], ("Other","⚠️"))
            ss = os.path.basename(v["screenshot"]) if v.get("screenshot","N/A")!="N/A" else ""
            ss_link = f'<a href="screenshots/{ss}" target="_blank">📷 View</a>' if ss else "—"
            rows += f"""<tr>
<td style="text-align:center">{i}</td>
<td><span class="cat cat-{cat.lower()}">{icon} {cat}</span></td>
<td><code>{v['type']}</code></td>
<td>{v.get('start_time','—')}</td>
<td>{v.get('end_time','—')}</td>
<td>{v.get('duration','—')}</td>
<td><span class="conf">{v.get('confidence',0):.0%}</span></td>
<td style="font-size:0.82em;color:#6b7280;max-width:200px">{v.get('description','')[:80]}</td>
<td>{ss_link}</td></tr>"""

        cats_html = ""
        for cat, count in r.get("category_summary",{}).items():
            _, icon = next(((c,ic) for t,(c,ic) in VIOLATION_CATEGORIES.items() if c==cat),(cat,"⚠️"))
            cats_html += f'<div class="cat-pill"><span class="cat cat-{cat.lower()}">{icon} {cat}</span><span class="cnt">{count}</span></div>'

        audit_rows = ""
        for a in (r.get("audit_trail") or [])[:12]:
            fn = os.path.basename(a.get("path",""))
            audit_rows += f'<a href="audit_trail/{fn}" target="_blank" class="audit-thumb">📸 {a.get("timestamp","")}</a>'

        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Double Proctoring Report</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0f172a;color:#e2e8f0;padding:2rem;font-size:14px}}
h1{{font-size:1.7rem;font-weight:700;color:#f8fafc}}
h2{{font-size:0.85rem;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.08em;margin:1.5rem 0 .6rem}}
.header{{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:1.5rem}}
.risk{{padding:.35rem 1rem;border-radius:999px;font-weight:700;font-size:.95rem;color:#fff;background:{rc}}}
.meta{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.8rem;margin-bottom:1.2rem}}
.mc{{background:#1e293b;border-radius:.75rem;padding:.9rem 1.1rem}}
.mc .lbl{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
.mc .val{{font-size:1.2rem;font-weight:700;margin-top:.2rem;color:#f1f5f9}}
.cats{{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:1.2rem}}
.cat-pill{{display:flex;align-items:center;gap:.4rem;background:#1e293b;padding:.3rem .7rem;border-radius:.5rem}}
.cnt{{font-weight:700;color:#f1f5f9}}
table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:.75rem;overflow:hidden;font-size:.85rem}}
th{{background:#0f172a;padding:.65rem .9rem;text-align:left;color:#64748b;font-weight:600;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}}
td{{padding:.7rem .9rem;border-bottom:1px solid #0f172a}}
tr:hover td{{background:#263348}}
code{{background:#0f172a;padding:.1rem .35rem;border-radius:.25rem;font-size:.8rem;color:#94a3b8}}
a{{color:#60a5fa;text-decoration:none}}a:hover{{text-decoration:underline}}
.cat{{padding:.15rem .5rem;border-radius:.35rem;font-size:.75rem;font-weight:600}}
.cat-screen{{background:#7f1d1d;color:#fca5a5}}
.cat-webcam{{background:#4a1d96;color:#c4b5fd}}
.cat-audio{{background:#713f12;color:#fde68a}}
.cat-process{{background:#1e3a5f;color:#93c5fd}}
.cat-other{{background:#1e293b;color:#94a3b8}}
.conf{{background:#172435;padding:.1rem .4rem;border-radius:.25rem;font-weight:700;color:#60a5fa}}
.audit-thumbs{{display:flex;flex-wrap:wrap;gap:.5rem}}
.audit-thumb{{background:#1e293b;padding:.3rem .7rem;border-radius:.5rem;font-size:.78rem}}
.no-v{{text-align:center;padding:3rem;color:#22c55e;font-size:1rem}}
footer{{margin-top:2rem;color:#475569;font-size:.78rem;text-align:center}}
</style></head><body>
<div class="header">
  <div>
    <h1>🔒 Double Proctoring Report</h1>
    <p style="color:#64748b;margin-top:.3rem">Generated: {r['generated_at']} &nbsp;|&nbsp; Mode: {r.get('mode','full').upper()}</p>
  </div>
  <span class="risk">Risk: {risk}</span>
</div>
<div class="meta">
  <div class="mc"><div class="lbl">Video</div><div class="val" style="font-size:.9rem">{r['video_file']}</div></div>
  <div class="mc"><div class="lbl">Duration</div><div class="val">{r['video_duration']}</div></div>
  <div class="mc"><div class="lbl">Frames</div><div class="val">{r['frames_analyzed']}</div></div>
  <div class="mc"><div class="lbl">Process time</div><div class="val">{r['processing_time']}</div></div>
  <div class="mc"><div class="lbl">Total violations</div><div class="val" style="color:{rc}">{r['total_violations']}</div></div>
</div>
<h2>Violation categories</h2>
<div class="cats">{cats_html if cats_html else '<span style="color:#64748b">None</span>'}</div>
<h2>Violations timeline</h2>
{'<table><thead><tr><th>#</th><th>Category</th><th>Type</th><th>Start</th><th>End</th><th>Duration</th><th>Confidence</th><th>Description</th><th>Evidence</th></tr></thead><tbody>'+rows+'</tbody></table>' if r['violations'] else '<div class="no-v">✅ No violations detected. Session appears clean.</div>'}
{('<h2>Audit trail</h2><div class="audit-thumbs">'+audit_rows+'</div>') if audit_rows else ''}
<footer>Double Proctoring Analyzer v2.0 — Screen + Webcam + Audio + Process</footer>
</body></html>"""

    def _render_pdf(self, report: Dict[str, Any], output_path: Path) -> None:
        """Build a printable ReportLab report with summary, timeline, and evidence."""
        return self._render_compact_pdf(report, output_path)

        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_RIGHT
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError as exc:
            raise RuntimeError(
                "PDF generation requires reportlab. Install dependencies with "
                "'pip install -r requirements.txt'."
            ) from exc

        navy = colors.HexColor("#0F172A")
        slate = colors.HexColor("#475569")
        pale = colors.HexColor("#E2E8F0")
        panel = colors.HexColor("#F8FAFC")
        risk_hex = {"CLEAN": "#16A34A", "LOW": "#D97706", "MEDIUM": "#EA580C", "HIGH": "#DC2626"}
        risk = report["risk_level"]
        risk_color = colors.HexColor(risk_hex.get(risk, "#475569"))

        doc = SimpleDocTemplate(
            str(output_path), pagesize=A4, title="Double Proctoring Report",
            author="Screen Analyzer", leftMargin=36, rightMargin=36,
            topMargin=36, bottomMargin=42,
        )
        base = getSampleStyleSheet()
        title = ParagraphStyle("PdfTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=colors.white)
        subtitle = ParagraphStyle("PdfSubtitle", parent=base["Normal"], fontSize=8.5, leading=11, textColor=colors.HexColor("#CBD5E1"))
        section = ParagraphStyle("PdfSection", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=navy, spaceBefore=16, spaceAfter=7)
        body = ParagraphStyle("PdfBody", parent=base["BodyText"], fontSize=8.5, leading=11, textColor=navy)
        small = ParagraphStyle("PdfSmall", parent=body, fontSize=7.5, leading=9)
        header_text = ParagraphStyle("PdfHeader", parent=small, fontName="Helvetica-Bold", textColor=colors.white)
        story = []

        header = Table([[
            [Paragraph("DOUBLE PROCTORING REPORT", title), Paragraph("Screen, webcam, audio and process-analysis evidence", subtitle)],
            Paragraph("<b>RISK LEVEL</b><br/><font size=16><b>{}</b></font>".format(escape(risk)), ParagraphStyle("PdfRisk", parent=subtitle, alignment=TA_RIGHT, textColor=colors.white, leading=15)),
        ]], colWidths=[4.85 * inch, 2.05 * inch])
        header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), navy), ("BACKGROUND", (1, 0), (1, 0), risk_color),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (0, 0), 16),
            ("RIGHTPADDING", (0, 0), (-1, -1), 16), ("TOPPADDING", (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ]))
        story.extend([header, Spacer(1, 12)])

        meta_items = [
            ("VIDEO FILE", report["video_file"]), ("VIDEO DURATION", report["video_duration"]),
            ("FRAMES ANALYZED", str(report["frames_analyzed"])), ("PROCESSING TIME", report["processing_time"]),
            ("ANALYSIS MODE", report.get("mode", "full").upper()), ("GENERATED", report["generated_at"].replace("T", " ")[:19]),
        ]
        meta = [Paragraph('<font color="#64748B" size="7"><b>{}</b></font><br/><font size="9"><b>{}</b></font>'.format(escape(label), escape(value)), body) for label, value in meta_items]
        meta_table = Table([meta[:3], meta[3:]], colWidths=[2.37 * inch] * 3)
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), panel), ("GRID", (0, 0), (-1, -1), 0.35, pale),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ]))
        story.extend([meta_table, Paragraph("Analysis summary", section)])

        categories = report.get("category_summary", {})
        breakdown = ", ".join("{}: {}".format(name, count) for name, count in categories.items()) or "No violations detected"
        summary = Table([[
            Paragraph('<b>Total incidents</b><br/><font size="20" color="{}"><b>{}</b></font>'.format(risk_hex.get(risk, "#475569"), report["total_violations"]), body),
            Paragraph('<b>Categories flagged</b><br/><font size="20"><b>{}</b></font>'.format(len(categories)), body),
            Paragraph("<b>Breakdown</b><br/>" + escape(breakdown), small),
        ]], colWidths=[1.6 * inch, 1.7 * inch, 3.8 * inch])
        summary.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), panel), ("BOX", (0, 0), (-1, -1), 0.5, pale),
            ("LINEBEFORE", (1, 0), (2, 0), 0.5, pale), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.extend([summary, Paragraph("Violation timeline", section)])

        violations = report["violations"]
        if not violations:
            story.append(Paragraph("No violations were detected. The session appears clean.", body))
        else:
            rows = [[Paragraph(label, header_text) for label in ("#", "Category", "Violation", "Time range", "Confidence", "Description")]]
            for number, violation in enumerate(violations, 1):
                category, _ = VIOLATION_CATEGORIES.get(violation["type"], ("Other", ""))
                time_range = "{} – {}".format(violation.get("start_time", "—"), violation.get("end_time", "—"))
                rows.append([
                    Paragraph(str(number), small), Paragraph(escape(category), small),
                    Paragraph(escape(violation["type"].replace("_", " ").title()), small),
                    Paragraph(escape(time_range), small), Paragraph("{:.0%}".format(violation.get("confidence", 0)), small),
                    Paragraph(escape(str(violation.get("description", "—"))), small),
                ])
            timeline = Table(rows, colWidths=[0.3 * inch, 0.72 * inch, 1.15 * inch, 1.05 * inch, 0.65 * inch, 3.25 * inch], repeatRows=1)
            timeline.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), navy), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, panel]),
                ("GRID", (0, 0), (-1, -1), 0.3, pale), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(timeline)

        evidence = [item for item in violations if Path(item.get("screenshot", "")).is_file()]
        if evidence:
            story.extend([PageBreak(), Paragraph("Incident evidence", section)])
            for number, violation in enumerate(evidence, 1):
                screenshot = Path(violation["screenshot"])
                try:
                    image = Image(str(screenshot))
                    image._restrictSize(6.7 * inch, 4.65 * inch)
                    caption = Paragraph("<b>{}. {}</b> &nbsp; {} &nbsp; Confidence: {:.0%}<br/>{}".format(number, escape(violation["type"].replace("_", " ").title()), escape(str(violation.get("start_time", "—"))), violation.get("confidence", 0), escape(str(violation.get("description", "No description provided.")))), body)
                    story.extend([KeepTogether([caption, Spacer(1, 5), image]), Spacer(1, 14)])
                except Exception:
                    story.append(Paragraph("Evidence image unavailable: {}".format(escape(screenshot.name)), small))

        def footer(canvas, current_doc):
            canvas.saveState()
            canvas.setStrokeColor(pale)
            canvas.line(current_doc.leftMargin, 25, A4[0] - current_doc.rightMargin, 25)
            canvas.setFont("Helvetica", 7.5)
            canvas.setFillColor(slate)
            canvas.drawString(current_doc.leftMargin, 14, "Double Proctoring Analyzer")
            canvas.drawRightString(A4[0] - current_doc.rightMargin, 14, "Page {}".format(current_doc.page))
            canvas.restoreState()

        doc.build(story, onFirstPage=footer, onLaterPages=footer)

    def _render_compact_pdf(self, report: Dict[str, Any], output_path: Path) -> None:
        """Render the compact, incident-first format used by the reference report."""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        navy = colors.HexColor("#111827")
        gray = colors.HexColor("#6B7280")
        border = colors.HexColor("#D1D5DB")
        styles = getSampleStyleSheet()
        title = ParagraphStyle("CompactTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=navy, spaceAfter=4)
        meta = ParagraphStyle("CompactMeta", parent=styles["Normal"], fontSize=8.5, leading=12, textColor=gray)
        heading = ParagraphStyle("CompactHeading", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=navy, spaceBefore=15, spaceAfter=7)
        body = ParagraphStyle("CompactBody", parent=styles["BodyText"], fontSize=8.5, leading=12, textColor=navy)
        incident_title = ParagraphStyle("IncidentTitle", parent=body, fontName="Helvetica-Bold", fontSize=10, leading=13)
        doc = SimpleDocTemplate(str(output_path), pagesize=A4, title="Screen Analyzer — Proctoring Report", leftMargin=46, rightMargin=46, topMargin=42, bottomMargin=38)
        story = [Paragraph("Screen Analyzer — Proctoring Report", title)]
        duration = int(report.get("video_duration_seconds", 0))
        duration_text = "{:02d}:{:02d}:{:02d}".format(duration // 3600, (duration % 3600) // 60, duration % 60)
        sample_fps = report.get("sample_fps")
        sample_text = "Sampled @ {} fps".format(sample_fps if sample_fps is not None else "—")
        story.extend([
            Paragraph("Source video: {}".format(escape(report["video_file"])), meta),
            Paragraph("Duration: {} &nbsp; | &nbsp; {} &nbsp; | &nbsp; Model: {}".format(duration_text, escape(sample_text), escape(str(report.get("model_name", "Screen Analyzer detectors")))), meta),
            Spacer(1, 8),
        ])

        violations = report["violations"]
        total_flagged = sum(float(item.get("duration_seconds", 0)) for item in violations)
        counts = report.get("violation_summary", {})
        metric_rows = [[Paragraph("<b>Metric</b>", body), Paragraph("<b>Value</b>", body)], ["Total incidents", str(len(violations))], ["Total flagged time", "{:.0f}s".format(total_flagged)]]
        for violation_type, count in counts.items():
            metric_rows.append(["• " + violation_type, str(count)])
        metrics = Table(metric_rows, colWidths=[4.7 * inch, 1.55 * inch])
        metrics.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.35, border), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTNAME", (0, 3), (0, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 3), (0, -1), navy), ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([metrics, Paragraph("Detected Violations", heading)])
        for index, violation in enumerate(violations, 1):
            name = violation["type"]
            start, end = violation.get("start_time", "—"), violation.get("end_time", "—")
            incident = Table([
                ["Start", escape(start), "End", escape(end)],
                ["Duration", escape(str(violation.get("duration", "—"))), "Frames flagged", str(violation.get("frames_flagged", 1))],
                ["Avg confidence", "{:.2f}".format(violation.get("avg_confidence", violation.get("confidence", 0))), "", ""],
            ], colWidths=[1.15 * inch, 2.0 * inch, 1.35 * inch, 1.75 * inch])
            incident.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.3, border), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F9FAFB")),
                ("BACKGROUND", (2, 0), (2, 1), colors.HexColor("#F9FAFB")), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, 1), "Helvetica-Bold"), ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            details = Table([
                [Paragraph("<b>Start</b>", body), Paragraph(escape(start), body)],
                [Paragraph("<b>End</b>", body), Paragraph(escape(end), body)],
                [Paragraph("<b>Duration</b>", body), Paragraph(escape(str(violation.get("duration", "-"))), body)],
                [Paragraph("<b>Frames flagged</b>", body), Paragraph(str(violation.get("frames_flagged", 1)), body)],
                [Paragraph("<b>Avg confidence</b>", body), Paragraph("{:.2f}".format(violation.get("avg_confidence", violation.get("confidence", 0))), body)],
            ], colWidths=[1.25 * inch, 1.25 * inch])
            details.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            incident_content = [Paragraph(
                "#{} &nbsp; <i>{}</i> &nbsp; <font color=\"#6B7280\">({} &rarr; {})</font>".format(
                    index, escape(name), escape(start), escape(end)
                ),
                incident_title,
            )]
            screenshot_path = Path(violation.get("screenshot", ""))
            if screenshot_path.is_file():
                try:
                    screenshot = Image(str(screenshot_path))
                    screenshot._restrictSize(4.0 * inch, 3.25 * inch)
                    evidence = screenshot
                except Exception:
                    evidence = Paragraph("Screenshot could not be loaded: {}".format(escape(screenshot_path.name)), meta)
            else:
                evidence = Paragraph("No screenshot was captured for this incident.", meta)
            incident_card = Table([[details, evidence]], colWidths=[2.55 * inch, 4.05 * inch])
            incident_card.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.45, border), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]))
            incident_content.extend([Spacer(1, 5), incident_card])
            story.extend([KeepTogether(incident_content), Spacer(1, 18)])

        def footer(canvas, current_doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(gray)
            canvas.drawString(current_doc.leftMargin, 18, "Double Proctoring Analyzer")
            canvas.drawRightString(A4[0] - current_doc.rightMargin, 18, "Page {}".format(current_doc.page))
            canvas.restoreState()

        doc.build(story, onFirstPage=footer, onLaterPages=footer)
