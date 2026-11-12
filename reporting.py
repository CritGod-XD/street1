import json
import os
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)


DISTRESS_COLORS = {
    "C": colors.HexColor("#e24b3b"),
    "P": colors.HexColor("#ed9637"),
    "M": colors.HexColor("#328bd6"),
    "S": colors.HexColor("#e2c63b"),
}
DISTRESS_LABELS = {
    "C": "Cracks",
    "P": "Potholes",
    "M": "Maintenance cuts / patches",
    "S": "Sealant",
}


def _read_json(path, fallback=None):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError):
        return fallback


def _number(value, digits=1):
    try:
        number = float(value)
        if number != number or abs(number) == float("inf"):
            return "—"
        return f"{number:,.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _station(value):
    try:
        feet = max(0, int(round(float(value))))
        return f"{feet // 100:>d}+{feet % 100:02d}"
    except (TypeError, ValueError):
        return "—"


def _normal_name(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _pci_condition(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "Not rated"
    if score >= 85:
        return "Good"
    if score >= 70:
        return "Satisfactory"
    if score >= 55:
        return "Fair"
    if score >= 40:
        return "Poor"
    if score >= 25:
        return "Very Poor"
    if score >= 10:
        return "Serious"
    return "Failed"


def _sdi_condition(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "Not rated"
    if score >= 3.5:
        return "Good"
    if score > 2.4:
        return "Fair"
    return "Poor"


def _weighted_average(sections, key):
    values = []
    for section in sections:
        try:
            value = float(section.get(key))
            weight = float(section.get("len") or 0)
            if 0 <= weight and value == value:
                values.append((value, weight))
        except (TypeError, ValueError):
            continue
    total_weight = sum(weight for _, weight in values)
    if not values or total_weight <= 0:
        return None
    return sum(value * weight for value, weight in values) / total_weight


def _find_road_dataset(road_name, app_root):
    roads_root = os.path.join(app_root, "public", "static", "roads")
    if not os.path.isdir(roads_root):
        return None, []
    wanted = _normal_name(road_name)
    try:
        folders = sorted(os.listdir(roads_root))
    except OSError:
        return None, []
    for folder in folders:
        folder_path = os.path.join(roads_root, folder)
        if not os.path.isdir(folder_path):
            continue
        index_path = os.path.join(folder_path, "index.json")
        index = _read_json(index_path, {})
        if not isinstance(index, dict):
            continue
        if _normal_name(index.get("road_name")) != wanted:
            continue
        frame_rows = []
        for frame in index.get("frames", []):
            if not isinstance(frame, dict):
                continue
            image_name = os.path.basename(str(frame.get("image") or ""))
            annotation_name = os.path.basename(str(frame.get("annotation") or ""))
            if not image_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                continue
            image_path = os.path.join(folder_path, image_name)
            if not os.path.isfile(image_path):
                continue
            annotation_path = os.path.join(folder_path, annotation_name) if annotation_name else ""
            annotation = _read_json(annotation_path, {}) if annotation_path and os.path.isfile(annotation_path) else {}
            shapes = annotation.get("shapes", []) if isinstance(annotation, dict) else []
            frame_rows.append({
                "frame_id": str(frame.get("frame_id") or frame.get("frame") or len(frame_rows) + 1),
                "image_path": image_path,
                "width": int(frame.get("image_width") or 1640),
                "height": int(frame.get("image_height") or 787),
                "shapes": shapes if isinstance(shapes, list) else [],
            })
        return index, frame_rows
    return None, []


class AnnotatedFrameSheet(Flowable):
    """Compact sequential frame sheet with the source LabelMe polygons overlaid."""

    def __init__(self, frames, max_width):
        super().__init__()
        self.frames = frames
        self.max_width = max_width
        self.columns = 8
        self.gap = 2.2
        self.label_height = 7
        self.cell_width = (max_width - (self.columns - 1) * self.gap) / self.columns
        self.image_height = self.cell_width * 787 / 1640
        self.row_height = self.image_height + self.label_height + 2
        self.rows = (len(frames) + self.columns - 1) // self.columns
        self.width = max_width
        self.height = self.rows * self.row_height

    def wrap(self, avail_width, avail_height):
        self.width = min(self.max_width, avail_width)
        self.cell_width = (self.width - (self.columns - 1) * self.gap) / self.columns
        self.image_height = self.cell_width * 787 / 1640
        self.row_height = self.image_height + self.label_height + 2
        self.height = self.rows * self.row_height
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        for index, frame in enumerate(self.frames):
            row = index // self.columns
            column = index % self.columns
            x = column * (self.cell_width + self.gap)
            y = self.height - (row + 1) * self.row_height + self.label_height + 1
            image_width = self.cell_width
            image_height = self.image_height
            canvas.saveState()
            canvas.setStrokeColor(colors.HexColor("#d8dee5"))
            canvas.setLineWidth(0.35)
            canvas.rect(x, y, image_width, image_height, stroke=1, fill=0)
            try:
                canvas.drawImage(
                    frame["image_path"], x, y, image_width, image_height,
                    preserveAspectRatio=False, mask="auto"
                )
            except Exception:
                canvas.setFillColor(colors.HexColor("#eef1f4"))
                canvas.rect(x, y, image_width, image_height, stroke=0, fill=1)
            for shape in frame.get("shapes", []):
                label = str(shape.get("label") or "").strip().upper()
                color = DISTRESS_COLORS.get(label)
                points = shape.get("points") or []
                if not color or len(points) < 3:
                    continue
                path = canvas.beginPath()
                try:
                    first_x = x + float(points[0][0]) / max(1, frame["width"]) * image_width
                    first_y = y + image_height - float(points[0][1]) / max(1, frame["height"]) * image_height
                    path.moveTo(first_x, first_y)
                    for point in points[1:]:
                        px = x + float(point[0]) / max(1, frame["width"]) * image_width
                        py = y + image_height - float(point[1]) / max(1, frame["height"]) * image_height
                        path.lineTo(px, py)
                    path.close()
                    canvas.setStrokeColor(color)
                    canvas.setFillColor(color)
                    canvas.setLineWidth(0.42)
                    try:
                        canvas.setFillAlpha(0.18)
                        canvas.setStrokeAlpha(0.9)
                    except AttributeError:
                        pass
                    canvas.drawPath(path, stroke=1, fill=1)
                    try:
                        canvas.setFillAlpha(1)
                        canvas.setStrokeAlpha(1)
                    except AttributeError:
                        pass
                except (TypeError, ValueError, IndexError):
                    continue
            canvas.setFillColor(colors.HexColor("#53606c"))
            canvas.setFont("Helvetica", 5.7)
            canvas.drawString(x, y - 6.2, f"Frame {frame['frame_id']}")
            canvas.restoreState()


def build_road_report_pdf(run, all_runs, app_root):
    sections = sorted(
        [item for item in run.get("secs", []) if isinstance(item, dict)],
        key=lambda item: float(item.get("f0") or 0)
    )
    road_name = str(run.get("name") or "Unnamed road")
    pci = _weighted_average(sections, "pci")
    sdi = _weighted_average(sections, "sdi")
    if pci is None:
        try:
            pci = float(run.get("pci"))
        except (TypeError, ValueError):
            pci = None
    if sdi is None:
        try:
            sdi = float(run.get("sdi"))
        except (TypeError, ValueError):
            sdi = None
    length = sum(float(section.get("len") or 0) for section in sections)
    crack_instances = sum(int(float(section.get("cr") or 0)) for section in sections)
    crack_length = sum(float(section.get("crft") or 0) for section in sections)
    potholes = sum(int(float(section.get("pot") or 0)) for section in sections)
    patches = sum(int(float(section.get("pat") or 0)) for section in sections)
    distressed_area = _weighted_average(sections, "dpct")
    sample_count = sum(int(float(section.get("n") or 0)) for section in sections)

    pci_values = []
    sdi_values = []
    for item in all_runs:
        try:
            value = float(item.get("pci"))
            if 0 <= value <= 100:
                pci_values.append((value, str(item.get("key") or "")))
        except (TypeError, ValueError):
            pass
        try:
            value = float(item.get("sdi"))
            if 0 <= value <= 5:
                sdi_values.append((value, str(item.get("key") or "")))
        except (TypeError, ValueError):
            pass
    current_key = str(run.get("key") or "")
    pci_rank = 1 + sum(1 for value, key in pci_values if pci is not None and value < pci)
    sdi_rank = 1 + sum(1 for value, key in sdi_values if sdi is not None and value < sdi)

    start_coord = end_coord = None
    for section in sections:
        coords = section.get("g") or []
        if coords and start_coord is None:
            start_coord = coords[0]
        if coords:
            end_coord = coords[-1]

    dataset_index, frames = _find_road_dataset(road_name, app_root)
    annotation_counts = {key: 0 for key in DISTRESS_COLORS}
    for frame in frames:
        for shape in frame.get("shapes", []):
            label = str(shape.get("label") or "").strip().upper()
            if label in annotation_counts:
                annotation_counts[label] += 1

    buffer = __import__("io").BytesIO()
    page_width, page_height = A4
    left = 12 * mm
    right = 12 * mm
    top = 12 * mm
    bottom = 13 * mm
    usable_width = page_width - left - right

    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=right, leftMargin=left,
        topMargin=top, bottomMargin=bottom,
        title=f"{road_name} · StreetLens pavement condition report",
        author="StreetLens"
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportEyebrow", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=7, leading=9, textColor=colors.HexColor("#64748b"), spaceAfter=3
    ))
    styles.add(ParagraphStyle(
        name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=22, leading=25, alignment=TA_LEFT, textColor=colors.HexColor("#14263e"),
        spaceAfter=3
    ))
    styles.add(ParagraphStyle(
        name="ReportMeta", parent=styles["Normal"], fontSize=7.5, leading=10,
        textColor=colors.HexColor("#536170"), spaceAfter=5
    ))
    styles.add(ParagraphStyle(
        name="SectionHeadingSL", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=10, leading=12, textColor=colors.HexColor("#182a40"),
        spaceBefore=6, spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name="BodySL", parent=styles["BodyText"], fontSize=7.3, leading=9.5,
        textColor=colors.HexColor("#334155"), spaceAfter=2
    ))
    styles.add(ParagraphStyle(
        name="SmallSL", parent=styles["BodyText"], fontSize=6.3, leading=8,
        textColor=colors.HexColor("#64748b")
    ))
    styles.add(ParagraphStyle(
        name="MetricLabelSL", parent=styles["Normal"], fontSize=6.2, leading=7.5,
        textColor=colors.HexColor("#64748b")
    ))
    styles.add(ParagraphStyle(
        name="MetricValueSL", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=16, leading=18, textColor=colors.HexColor("#14263e")
    ))
    styles.add(ParagraphStyle(
        name="MetricSubSL", parent=styles["Normal"], fontSize=6.2, leading=7.5,
        textColor=colors.HexColor("#64748b")
    ))
    styles.add(ParagraphStyle(
        name="TableHeadSL", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=5.8, leading=7, textColor=colors.white
    ))
    styles.add(ParagraphStyle(
        name="TableCellSL", parent=styles["Normal"], fontSize=6.1, leading=7.4,
        textColor=colors.HexColor("#263445")
    ))
    styles.add(ParagraphStyle(
        name="TableCellBoldSL", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=6.1, leading=7.4, textColor=colors.HexColor("#17283e")
    ))

    def para(text, style="BodySL"):
        return Paragraph(str(text), styles[style])

    story = []
    story.append(para("COLLINGSWOOD, NJ  ·  PAVEMENT CONDITION INSPECTION REPORT", "ReportEyebrow"))
    story.append(para(escape(road_name), "ReportTitle"))
    start_text = f"{float(start_coord[0]):.5f}, {float(start_coord[1]):.5f}" if start_coord else "Not available"
    end_text = f"{float(end_coord[0]):.5f}, {float(end_coord[1]):.5f}" if end_coord else "Not available"
    story.append(para(
        f"Run: {escape(str(run.get('key') or '—'))}  ·  Start: {start_text}  ·  End: {end_text}"
        f"  ·  Survey date: not recorded in source  ·  Report generated {__import__('datetime').datetime.now().strftime('%d %b %Y')}",
        "ReportMeta"
    ))

    pci_condition = _pci_condition(pci)
    sdi_condition = _sdi_condition(sdi)
    metric_cells = [
        [para("PCI  ·  ASTM D6433", "MetricLabelSL"), para("SDI", "MetricLabelSL"),
         para("LENGTH RATED", "MetricLabelSL"), para("INSPECTION FRAMES", "MetricLabelSL")],
        [para(_number(pci, 1), "MetricValueSL"), para(_number(sdi, 2), "MetricValueSL"),
         para(f"{_number(length, 0)} ft", "MetricValueSL"),
         para(str(len(frames)) if frames else "Unavailable", "MetricValueSL")],
        [para(escape(pci_condition), "MetricSubSL"),
         para(escape(sdi_condition), "MetricSubSL"),
         para(f"{_number(length / 5280, 3)} mi rated", "MetricSubSL"),
         para("Sequential frame images" if frames else "No registered image folder", "MetricSubSL")]
    ]
    metric_table = Table(metric_cells, colWidths=[usable_width / 4] * 4)
    metric_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f5f8")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e0e8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d9e0e8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(metric_table)

    rank_parts = []
    if pci is not None and pci_values:
        rank_parts.append(f"PCI: {pci_rank} of {len(pci_values)} scored runs (lowest first)")
    if sdi is not None and sdi_values:
        rank_parts.append(f"SDI: {sdi_rank} of {len(sdi_values)} scored runs (lowest first)")
    if rank_parts:
        story.append(Spacer(1, 5))
        rank_table = Table([[para("  ·  ".join(rank_parts), "BodySL")]], colWidths=[usable_width])
        rank_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff6e6")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#ead8b5")),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(rank_table)

    story.append(para("What the survey shows", "SectionHeadingSL"))
    findings = (
        f"<b>{crack_instances:,}</b> recorded crack instances extend for "
        f"<b>{_number(crack_length, 1)} ft</b> across the scored sections.<br/>"
        f"Weighted distressed-area percentage: <b>{_number(distressed_area, 1)}%</b>.<br/>"
        f"<b>{potholes:,}</b> potholes and <b>{patches:,}</b> maintenance-cut / patch records "
        f"are recorded in the section data.<br/>"
        f"The source contains <b>{sample_count:,}</b> section-level sample elements across "
        f"<b>{len(sections)}</b> scored bins."
    )
    if pci is not None and pci < 40:
        action = "High priority — arrange a field review and rehabilitation assessment. The PCI band indicates substantial pavement distress; treatment selection and limits require engineering review."
    elif pci is not None and pci < 55:
        action = "Priority review — inspect the distressed locations and evaluate suitable repair or rehabilitation options. Confirm treatment limits in the field."
    elif pci is not None and pci < 70:
        action = "Plan maintenance review — prioritize localized defects and consider preventive maintenance where field conditions support it."
    else:
        action = "Continue routine monitoring and evaluate preventive maintenance based on field conditions."
    two_col = Table([[
        para(findings, "BodySL"),
        para(f"<b>Indicative follow-up (PCI screening band)</b><br/>{action}", "BodySL")
    ]], colWidths=[usable_width * 0.57, usable_width * 0.43])
    two_col.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#f6f8fa")),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#fff6e6")),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#d9e0e8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d9e0e8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(two_col)

    story.append(para("Distress summary · quantities available in the road dataset", "SectionHeadingSL"))
    distress_rows = [[
        para("DISTRESS", "TableHeadSL"), para("RECORDED COUNT", "TableHeadSL"),
        para("QUANTITY / VALUE", "TableHeadSL"), para("SOURCE FIELD", "TableHeadSL")
    ], [
        para("Crack instances", "TableCellBoldSL"), para(f"{crack_instances:,}", "TableCellSL"),
        para(f"{_number(crack_length, 1)} ft crack length", "TableCellSL"),
        para("cr / crft", "TableCellSL")
    ], [
        para("Distressed area", "TableCellBoldSL"), para("—", "TableCellSL"),
        para(f"{_number(distressed_area, 1)}% weighted by section length", "TableCellSL"),
        para("dpct", "TableCellSL")
    ], [
        para("Potholes", "TableCellBoldSL"), para(f"{potholes:,}", "TableCellSL"),
        para("Count only; area not supplied", "TableCellSL"),
        para("pot", "TableCellSL")
    ], [
        para("Maintenance cuts / patches", "TableCellBoldSL"), para(f"{patches:,}", "TableCellSL"),
        para("Count only; area not supplied", "TableCellSL"),
        para("pat", "TableCellSL")
    ]]
    distress_table = Table(distress_rows, colWidths=[
        usable_width * .27, usable_width * .15, usable_width * .40, usable_width * .18
    ], repeatRows=1)
    distress_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#24364c")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6f9")]),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d6dde5")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(distress_table)

    if sections:
        story.append(para("Section-level condition scores", "SectionHeadingSL"))
        header = ["BIN", "STATION", "LENGTH", "PCI", "PCI CONDITION", "SDI", "NDI", "LDI", "DISTRESSED %", "POTHOLES", "PATCHES"]
        section_rows = [[para(escape(value), "TableHeadSL") for value in header]]
        for section in sections:
            start = section.get("f0")
            end = section.get("f1")
            station = f"{_station(start)}–{_station(end)}"
            values = [
                str(section.get("bin", "—")), station, _number(section.get("len"), 0),
                _number(section.get("pci"), 1), _pci_condition(section.get("pci")),
                _number(section.get("sdi"), 2), _number(section.get("ndi"), 2),
                _number(section.get("ldi"), 2), _number(section.get("dpct"), 1),
                str(int(float(section.get("pot") or 0))),
                str(int(float(section.get("pat") or 0))),
            ]
            section_rows.append([para(escape(value), "TableCellSL") for value in values])
        widths = [23, 70, 38, 29, 49, 28, 28, 28, 48, 33, 33]
        scale = usable_width / sum(widths)
        section_table = Table(section_rows, colWidths=[value * scale for value in widths], repeatRows=1)
        section_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#24364c")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6f9")]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d6dde5")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(section_table)

        unit_values = []
        for section in sections:
            for unit in section.get("units", []):
                if isinstance(unit, dict) and unit.get("pci") is not None:
                    unit_values.append(_number(unit.get("pci"), 1))
        if unit_values:
            story.append(Spacer(1, 3))
            story.append(para(
                "<b>PCI unit scores recorded in source:</b> " + ", ".join(unit_values)
                + ". Unit-specific station limits are not supplied in this dataset.",
                "SmallSL"
            ))

    story.append(para("Basis and limitations", "SectionHeadingSL"))
    limitations = (
        "This report uses the active StreetLens Collingswood section dataset and current saved PCI / SDI score revisions. "
        "Run-level values are length-weighted from the section records where available. The source provides aggregate crack "
        "instances, crack length, distressed-area percentage, pothole count and maintenance-patch count. It does not provide "
        "distress severity classes, a longitudinal / transverse / pattern-crack split, wheel-path distribution, measured area "
        "for each pothole or patch, or a survey date. The indicative follow-up is a screening aid, not a final engineering "
        "recommendation. Confirm condition, treatment type and limits through field review."
    )
    story.append(para(limitations, "SmallSL"))

    story.append(PageBreak())
    story.append(para(escape(road_name) + " · ANNOTATED SURVEY IMAGERY", "ReportEyebrow"))
    story.append(para("Sequential road inspection frames", "SectionHeadingSL"))
    story.append(para(
        f"{len(frames)} image frames are available for this road. Frames are arranged in capture order, "
        "left to right and then top to bottom. Annotation polygons are drawn over their corresponding source frame.",
        "BodySL"
    ))
    legend_items = []
    for label in ("C", "P", "M", "S"):
        color = DISTRESS_COLORS[label].hexval()
        legend_items.append(
            f'<font color="{color}">■</font> <b>{label}</b> {DISTRESS_LABELS[label]}'
            f' ({annotation_counts[label]} polygons)'
        )
    story.append(para("   ·   ".join(legend_items), "SmallSL"))
    story.append(Spacer(1, 6))
    if frames:
        sheet = AnnotatedFrameSheet(frames, usable_width)
        story.append(sheet)
    else:
        story.append(Spacer(1, 20))
        story.append(para(
            "No road-specific frame index and image files are currently registered for this road. "
            "The score summary above is still generated from the available section dataset.",
            "BodySL"
        ))

    def draw_footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#d7dee7"))
        canvas.setLineWidth(0.4)
        canvas.line(left, 9 * mm, page_width - right, 9 * mm)
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(left, 5.5 * mm, f"StreetLens · {road_name} · pavement condition report")
        canvas.drawRightString(page_width - right, 5.5 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    safe_name = re.sub(r"[^a-z0-9]+", "-", road_name.casefold()).strip("-") or "road"
    return buffer.getvalue(), f"streetlens-{safe_name}-report.pdf"
