from __future__ import annotations

from pathlib import Path
import tempfile

import pymupdf

from services.form_definition_loader import FormDefinition


class FormPdfError(RuntimeError):
    """Raised when an OPXFORM PDF cannot be rendered."""


def render_form_pdf(
    form: FormDefinition,
    values: dict[str, object],
    *,
    output_path: str | Path | None = None,
) -> Path:
    """
    Overlay OPXFORM values onto the form's configured PDF template.

    OPXFORM v1 coordinate convention:
      - origin (0,0) is the upper-left corner
      - x increases to the right
      - y increases downward
      - units are PDF points (72 points = 1 inch)
    """
    pdf_def = form.pdf

    if not pdf_def:
        raise FormPdfError(
            f"Form '{form.name}' does not define a PDF template."
        )

    template_name = str(
        pdf_def.get("template", "")
    ).strip()

    if not template_name:
        raise FormPdfError(
            f"Form '{form.name}' has no PDF template filename."
        )

    # PDF template resides beside the .opxform file.
    template_path = (
        form.source_path.parent / template_name
    ).resolve()

    if not template_path.exists():
        raise FormPdfError(
            f"PDF template was not found:\n{template_path}"
        )

    fields = pdf_def.get("fields", [])

    if not isinstance(fields, list):
        raise FormPdfError(
            "'pdf.fields' must be a JSON array."
        )

    # Default preview goes into a temporary OutpostX directory.
    if output_path is None:
        safe_name = _safe_filename(form.form_id)

        temp_dir = Path(tempfile.gettempdir()) / "OutpostX"
        temp_dir.mkdir(parents=True, exist_ok=True)

        output_path = temp_dir / f"{safe_name}-preview.pdf"

    output_path = Path(output_path)

    try:
        doc = pymupdf.open(template_path)
    except Exception as exc:
        raise FormPdfError(
            f"Unable to open PDF template:\n{template_path}\n\n{exc}"
        ) from exc

    try:
        for mapping in fields:
            _render_field(
                doc,
                mapping,
                values,
            )

        # overwrite an existing preview file if needed
        if output_path.exists():
            output_path.unlink()

        doc.save(
            output_path,
            garbage=4,
            deflate=True,
        )

    except Exception as exc:
        raise FormPdfError(
            f"Unable to render form PDF:\n{exc}"
        ) from exc

    finally:
        doc.close()

    return output_path


def _render_field(
    doc: pymupdf.Document,
    mapping: dict,
    values: dict[str, object],
) -> None:
    """
    Render one mapped OPXFORM field onto its PDF page.
    """

    field_id = str(mapping.get("id", "")).strip()

    if not field_id:
        return

    # Optional display condition.
    #
    # Example:
    #   "show_if": "signed"
    #
    # means render this PDF field only when values["signed"] is true.
    show_if = str(mapping.get("show_if", "") or "").strip()

    if show_if:
        condition_value = values.get(show_if)

        if not bool(condition_value):
            return


    # The PDF field may display the value of another OPXFORM field.
    #
    # Example:
    #   "id": "signed"
    #   "source_id": "approved_by"
    source_id = str(
        mapping.get("source_id")
        or field_id
    ).strip()

    value = values.get(source_id)

    if value is None or value == "":
        return


    # Optional PDF-only text decoration.
    prefix = str(mapping.get("prefix", "") or "")
    suffix = str(mapping.get("suffix", "") or "")

    text = _pdf_value(value)

    if not text:
        return

    text = f"{prefix}{text}{suffix}"
    #---

    try:
        page_number = int(mapping.get("page", 1))
    except (TypeError, ValueError) as exc:
        raise FormPdfError(
            f"Field '{field_id}' has an invalid page number."
        ) from exc

    if page_number < 1 or page_number > len(doc):
        raise FormPdfError(
            f"Field '{field_id}' references invalid page {page_number}."
        )

    page = doc[page_number - 1]

    try:
        x = float(mapping["x"])
        y = float(mapping["y"])
        width = float(mapping["width"])
        height = float(mapping["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FormPdfError(
            f"Field '{field_id}' has invalid PDF coordinates."
        ) from exc

    try:
        font_size = float(mapping.get("font_size", 10))
    except (TypeError, ValueError) as exc:
        raise FormPdfError(
            f"Field '{field_id}' has an invalid font_size."
        ) from exc

    rect = pymupdf.Rect(
        x,
        y,
        x + width,
        y + height,
    )

    multiline = bool(mapping.get("multiline", False))
    wrap = bool(mapping.get("wrap", multiline))

    if multiline or wrap:
        _insert_textbox(
            page,
            rect,
            text,
            font_size,
            field_id,
        )
    else:
        _insert_single_line(
            page,
            rect,
            text,
            font_size,
        )


def _pdf_value(value: object) -> str:
    """
    Convert an OPXFORM value into printable PDF text.

    Checkbox:
      True  -> X
      False -> blank
    """
    if isinstance(value, bool):
        return "X" if value else ""

    return str(value).strip()


def _insert_single_line(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    text: str,
    font_size: float,
) -> None:
    """
    Place a single line of text using the upper-left mapping rectangle.
    """
    point = pymupdf.Point(
        rect.x0,
        rect.y0 + font_size,
    )

    page.insert_text(
        point,
        text,
        fontsize=font_size,
        fontname="helv",
    )


def _insert_textbox(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    text: str,
    font_size: float,
    field_id: str,
) -> None:
    """
    Render wrapped or multiline text inside a rectangle.
    """
    result = page.insert_textbox(
        rect,
        text,
        fontsize=font_size,
        fontname="helv",
        align=pymupdf.TEXT_ALIGN_LEFT,
    )

    # PyMuPDF returns a negative value when the text does not fit.
    if result < 0:
        raise FormPdfError(
            f"PDF field '{field_id}' does not fit within "
            f"its defined rectangle."
        )


def _safe_filename(text: str) -> str:
    """
    Convert form_id into a safe temporary filename.
    """
    return "".join(
        ch if ch.isalnum() or ch in ("-", "_", ".") else "_"
        for ch in text
    )


def render_coordinate_grid(
    template_path: str | Path,
    output_path: str | Path,
    *,
    # spacing: int = 36,
    spacing: int = 18,
) -> Path:
    """
    Create a temporary copy of a PDF with an upper-left coordinate grid.

    OPXFORM coordinate convention:
      - origin (0,0) is upper-left
      - x increases to the right
      - y increases downward
      - units are PDF points

    Default spacing:
      36 points = 0.5 inch
    """
    template_path = Path(template_path).expanduser().resolve()
    output_path = Path(output_path).expanduser().resolve()

    if not template_path.exists():
        raise FormPdfError(
            f"PDF template was not found:\n{template_path}"
        )

    try:
        doc = pymupdf.open(template_path)
    except Exception as exc:
        raise FormPdfError(
            f"Unable to open PDF template:\n{template_path}\n\n{exc}"
        ) from exc

    try:
        for page in doc:
            width = page.rect.width
            height = page.rect.height

            # Vertical grid lines
            x = 0
            while x <= width:
                page.draw_line(
                    pymupdf.Point(x, 0),
                    pymupdf.Point(x, height),
                    width=0.25,
                )

                if x > 0:
                    page.insert_text(
                        pymupdf.Point(x + 2, 10),
                        str(int(x)),
                        fontsize=6,
                    )

                x += spacing

            # Horizontal grid lines
            y = 0
            while y <= height:
                page.draw_line(
                    pymupdf.Point(0, y),
                    pymupdf.Point(width, y),
                    width=0.25,
                )

                if y > 0:
                    page.insert_text(
                        pymupdf.Point(2, y - 2),
                        str(int(y)),
                        fontsize=6,
                    )

                y += spacing

        if output_path.exists():
            output_path.unlink()

        doc.save(
            output_path,
            garbage=4,
            deflate=True,
        )

    except Exception as exc:
        raise FormPdfError(
            f"Unable to create coordinate-grid PDF:\n{exc}"
        ) from exc

    finally:
        doc.close()

    return output_path