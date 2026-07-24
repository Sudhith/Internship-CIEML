import os
from pathlib import Path
from fpdf import FPDF
from PIL import Image


def safe_text(s: str) -> str:
    try:
        return s.encode("latin-1").decode("latin-1")
    except Exception:
        return s.encode("utf-8", errors="replace").decode("latin-1", errors="replace")


def gather_text_summaries(outputs_dir: Path) -> list[tuple[str, str]]:
    summaries = []
    for i in range(1, 9):
        p = outputs_dir / f"phase{i}" / f"PHASE{i}_SUMMARY.md"
        if p.exists():
            summaries.append((f"Phase {i}", p.read_text(encoding="utf-8")))
    # Phase1 is PHASE1_SUMMARY.md already covered; also include combined if present
    combined = outputs_dir / "COMBINED_PHASE_SUMMARIES.md"
    if combined.exists():
        summaries.insert(0, ("Combined Summary", combined.read_text(encoding="utf-8")))
    # Add phase5 artifacts (JSON) as text if present
    ph5_folder = outputs_dir / "phase5"
    if ph5_folder.exists():
        for fname in ["stage08_explainability_consensus.json", "stage_m1_hypothesis_register.json"]:
            p = ph5_folder / fname
            if p.exists():
                summaries.append((fname, p.read_text(encoding="utf-8")))
    return summaries


def gather_figures(outputs_dir: Path) -> list[Path]:
    imgs = []
    for root, _, files in os.walk(outputs_dir):
        for f in files:
            if f.lower().endswith((".png", ".jpg", ".jpeg")) and f.lower().startswith("fig_"):
                imgs.append(Path(root) / f)
    # also include any other pngs in figures folders
    for root, _, files in os.walk(outputs_dir):
        for f in files:
            if f.lower().endswith((".png", ".jpg", ".jpeg")) and "fig" in f.lower():
                p = Path(root) / f
                if p not in imgs:
                    imgs.append(p)
    return sorted(imgs)


class PDFReport(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 8, safe_text("CIEML Detailed Report"), ln=True, align="C")
        self.ln(2)


def add_text_section(pdf: PDFReport, title: str, text: str):
    # Render the text into an image and include that image in the PDF to avoid
    # FPDF text-wrapping limitations for very long JSON or markdown lines.
    from PIL import Image, ImageDraw, ImageFont
    import textwrap

    report_imgs_dir = Path(__file__).resolve().parents[1] / "outputs" / "report_images"
    report_imgs_dir.mkdir(parents=True, exist_ok=True)
    safe_title = title.replace(" ", "_")[:60]
    out_png = report_imgs_dir / f"summary_{safe_title}.png"

    # Prepare wrapped text
    wrapper = textwrap.TextWrapper(width=120)
    lines = []
    lines.append(title)
    lines.append("")
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        wrapped = wrapper.wrap(paragraph)
        if not wrapped:
            lines.append(paragraph)
        else:
            lines.extend(wrapped)

    # choose font
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    # estimate image size
    max_chars = max(len(l) for l in lines) if lines else 0
    char_w, char_h = (6, 11)
    img_w = max(800, min(2000, max_chars * char_w + 40))
    img_h = max(600, len(lines) * char_h + 40)

    img = Image.new("RGB", (img_w, img_h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    y = 10
    for ln in lines:
        draw.text((10, y), safe_text(ln), fill=(0, 0, 0), font=font)
        y += char_h
    img.save(out_png)
    # include image in PDF
    add_image(pdf, out_png, caption=title)


def add_image(pdf: PDFReport, img_path: Path, caption: str = ""):
    try:
        im = Image.open(img_path)
        width, height = im.size
        # convert px to mm (approx at 96 DPI)
        dpi = im.info.get("dpi", (96, 96))[0]
        mm_width = width / dpi * 25.4
        mm_height = height / dpi * 25.4
        max_w = pdf.w - 20
        max_h = pdf.h - 40
        scale = min(1, max_w / mm_width, max_h / mm_height)
        disp_w = mm_width * scale
        disp_h = mm_height * scale
        pdf.add_page()
        x = (pdf.w - disp_w) / 2
        y = pdf.get_y() + 5
        pdf.image(str(img_path), x=x, y=y, w=disp_w, h=disp_h)
        if caption:
            pdf.ln(disp_h / 2)
            pdf.set_font("Helvetica", "I", 9)
            import textwrap
            for chunk in textwrap.wrap(safe_text(caption), width=120):
                pdf.multi_cell(0, 5, chunk)
    except Exception as e:
        pdf.add_page()
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, safe_text(f"Could not include image {img_path.name}: {e}"))


def main():
    base = Path(__file__).resolve().parents[1]
    outputs = base / "outputs"
    pdf_path = outputs / "DETAILED_CIEML_REPORT.pdf"

    summaries = gather_text_summaries(outputs)
    figs = gather_figures(outputs)

    pdf = PDFReport()
    pdf.set_auto_page_break(True, margin=15)

    # Title page
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, safe_text("CIEML - Detailed Pipeline Report"), ln=True, align="C")
    pdf.ln(4)
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 8, safe_text(f"Generated from outputs at: {outputs}"), ln=True, align="C")
    pdf.ln(8)

    # Add summaries
    for title, content in summaries:
        add_text_section(pdf, title, content)

    # Embed figures
    for p in figs:
        add_image(pdf, p, caption=str(p.relative_to(outputs)))

    pdf.output(str(pdf_path))
    print(f"Wrote PDF: {pdf_path}")


if __name__ == "__main__":
    main()


def safe_text(s: str) -> str:
    try:
        return s.encode("latin-1").decode("latin-1")
    except Exception:
        return s.encode("utf-8", errors="replace").decode("latin-1", errors="replace")
