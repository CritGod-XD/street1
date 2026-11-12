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
        self.columns = 18
        self.gap = 1.15
        self.label_height = 5
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
            clip = canvas.beginPath()
            clip.rect(x, y, image_width, image_height)
            canvas.clipPath(clip, stroke=0, fill=0)
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
    opposite_run = None
    direction_swap = {"N": "S", "S": "N", "E": "W", "W": "E"}
    name_parts = road_name.rsplit(" ", 1)
    if len(name_parts) == 2 and name_parts[-1].upper() in direction_swap:
        opposite_name = name_parts[0] + " " + direction_swap[name_parts[-1].upper()]
        opposite_run = next(
            (item for item in all_runs if str(item.get("name") or "").casefold() == opposite_name.casefold()),
            None,
        )

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
        [para("PCI  ·  PAVEMENT CONDITION INDEX", "MetricLabelSL"), para("SDI", "MetricLabelSL"),
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
    if opposite_run:
        opposite_pci = opposite_run.get("pci")
        opposite_sdi = opposite_run.get("sdi")
        story.append(Spacer(1, 3))
        story.append(para(
            f"<b>Opposite direction comparison · {escape(str(opposite_run.get('name') or ''))}:</b> "
            f"PCI {_number(opposite_pci, 1)} ({escape(_pci_condition(opposite_pci))})"
            f"  ·  SDI {_number(opposite_sdi, 2)} ({escape(_sdi_condition(opposite_sdi))}).",
            "SmallSL"
        ))

    story.append(para("What the survey shows", "SectionHeadingSL"))
    findings = (
        f"<b>{crack_instances:,}</b> recorded crack instances extend for "
        f"<b>{_number(crack_length, 1)} ft</b> across the scored sections.<br/>"
        f"Weighted distressed-area percentage: <b>{_number(distressed_area, 1)}%</b>.<br/>"
        f"<b>{potholes:,}</b> potholes and <b>{patches:,}</b> maintenance-cut / patch records "
        f"are recorded in the section data.<br/>"
        f"The source contains <b>{sample_count:,}</b> source micro-sections across "
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

    story.append(para("Distress summary quantities as booked for PCI, whole road", "SectionHeadingSL"))
    distress_rows = [[
        para("DISTRESS", "TableHeadSL"), para("SEVERITY", "TableHeadSL"),
        para("COUNT", "TableHeadSL"), para("QUANTITY", "TableHeadSL"),
        para("DENSITY %", "TableHeadSL"), para("IN WHEEL PATHS", "TableHeadSL")
    ], [
        para("Cracking (combined)", "TableCellBoldSL"), para("Not recorded", "TableCellSL"),
        para(f"{crack_instances:,}", "TableCellSL"), para(f"{_number(crack_length, 1)} ft", "TableCellSL"),
        para("—", "TableCellSL"), para("—", "TableCellSL")
    ], [
        para("Pattern / block cracking", "TableCellBoldSL"), para("Not separately classified", "TableCellSL"),
        para("—", "TableCellSL"), para("—", "TableCellSL"), para("—", "TableCellSL"), para("—", "TableCellSL")
    ], [
        para("Maintenance cuts / patches", "TableCellBoldSL"), para("Not recorded", "TableCellSL"),
        para(f"{patches:,}", "TableCellSL"), para("—", "TableCellSL"), para("—", "TableCellSL"), para("—", "TableCellSL")
    ], [
        para("Potholes", "TableCellBoldSL"), para("Not recorded", "TableCellSL"),
        para(f"{potholes:,}", "TableCellSL"), para("—", "TableCellSL"), para("—", "TableCellSL"), para("—", "TableCellSL")
    ]]
    distress_table = Table(distress_rows, colWidths=[
        usable_width * .22, usable_width * .19, usable_width * .10,
        usable_width * .17, usable_width * .13, usable_width * .19
    ], repeatRows=1)
    distress_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#303840")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#777777")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(distress_table)
    story.append(para(
        "* StreetLens currently stores aggregate crack count and length. It does not separately store longitudinal, "
        "transverse or pattern-crack quantities, severity, density or wheel-path percentages. Dashes indicate unavailable "
        "source measurements, not zero distress.", "SmallSL"
    ))

    if sections:
        story.append(para("PCI by sample unit                                      SDI by 0.1 mile bin", "SectionHeadingSL"))
        unit_scores = []
        seen_unit_scores = set()
        for section in sections:
            for unit in section.get("units", []):
                if not isinstance(unit, dict) or unit.get("pci") is None:
                    continue
                value = round(float(unit.get("pci")), 1)
                if value not in seen_unit_scores:
                    seen_unit_scores.add(value)
                    unit_scores.append(value)
        pci_rows = [[
            para("UNIT", "TableHeadSL"), para("PCI", "TableHeadSL"),
            para("CONDITION", "TableHeadSL"), para("LARGEST DEDUCTS", "TableHeadSL")
        ]]
        for index, value in enumerate(unit_scores, 1):
            pci_rows.append([
                para(str(index), "TableCellSL"), para(_number(value, 1), "TableCellSL"),
                para(_pci_condition(value), "TableCellSL"), para("Not supplied", "TableCellSL")
            ])
        if len(pci_rows) == 1:
            pci_rows.append([para("—", "TableCellSL")] * 4)
        sdi_rows = [[
            para("BIN", "TableHeadSL"), para("STATION", "TableHeadSL"),
            para("NDI", "TableHeadSL"), para("LDI", "TableHeadSL"),
            para("SDI", "TableHeadSL"), para("DISTRESSED AREA", "TableHeadSL")
        ]]
        for section in sections:
            sdi_rows.append([
                para(str(section.get("bin", "—")), "TableCellSL"),
                para(f"{_station(section.get('f0'))} to {_station(section.get('f1'))}", "TableCellSL"),
                para(_number(section.get("ndi"), 2), "TableCellSL"),
                para(_number(section.get("ldi"), 2), "TableCellSL"),
                para(_number(section.get("sdi"), 2), "TableCellSL"),
                para(f"{_number(section.get('dpct'), 1)}%", "TableCellSL")
            ])
        pci_table = Table(pci_rows, colWidths=[usable_width * .035, usable_width * .045, usable_width * .075, usable_width * .14], repeatRows=1)
        sdi_table = Table(sdi_rows, colWidths=[usable_width * .045, usable_width * .10, usable_width * .055, usable_width * .055, usable_width * .055, usable_width * .10], repeatRows=1)
        common_table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#303840")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#777777")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        pci_table.setStyle(TableStyle(common_table_style))
        sdi_table.setStyle(TableStyle(common_table_style))
        paired_tables = Table([[pci_table, sdi_table]], colWidths=[usable_width * .43, usable_width * .57])
        paired_tables.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(paired_tables)
        story.append(para(
            "PCI unit scores are available, but unit station limits and largest deducts are not included in the current "
            "StreetLens section records. The SDI table uses the supplied scored bins.",
            "SmallSL"
        ))

    story.append(para("Basis and limits", "SectionHeadingSL"))
    limitations = (
        "This report follows the pavement rehabilitation candidate summary format and uses the active StreetLens Collingswood section dataset and current saved PCI / SDI score revisions. "
        "Run-level values are length-weighted from the section records where available. The source provides aggregate crack "
        "instances, crack length, distressed-area percentage, pothole count and maintenance-patch count. It does not provide "
        "distress severity classes, a longitudinal / transverse / pattern-crack split, sample-unit station limits or largest deducts, wheel-path distribution, measured area "
        "for each pothole or patch, or a survey date. The indicative follow-up is a screening aid, not a final engineering "
        "recommendation. Confirm condition, treatment type and limits through field review."
    )
    story.append(para(limitations, "SmallSL"))

    story.append(PageBreak())
    story.append(para(escape(road_name) + "   DRAFT", "ReportEyebrow"))
    story.append(para("Annotated survey imagery", "SectionHeadingSL"))
    story.append(para(
        f"Survey imagery for {escape(road_name)}. Frames are arranged in capture order, "
        "left to right and continues on the next row. Annotation polygons are drawn over their corresponding source frame.",
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
