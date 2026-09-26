"""
Build: 
cd outpostpmx/outpostx
pyinstaller --onefile --clean --name pdf_coordinate_grid tools\pdf_coordinate_grid.py

Test Cases when running the executable:
1. pdf_coordinate_grid
2. pdf_coordinate_grid --help
3. pdf_coordinate_grid --version
4. pdf_coordinate_grid SCCO.ICS213.pdf
5. pdf_coordinate_grid bogus.pdf
6. pdf_coordinate_grid something.txt
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pymupdf

VERSION = "1.0"

MAJOR_SPACING = 18
MINOR_SPACING = 3
TICK_LENGTH = 2
TICK_WIDTH = 0.15
LABEL_FONT_SIZE = 6

def create_coordinate_grid(
    input_path: Path,
    output_path: Path,
) -> None:
    """
    Create a copy of a PDF with an upper-left coordinate grid.

    Coordinate convention:
      - origin (0,0) is upper-left
      - x increases to the right
      - y increases downward
      - units are PDF points
      - 72 points = 1 inch
    """

    doc = pymupdf.open(input_path)

    try:
        for page in doc:
            width = page.rect.width
            height = page.rect.height

            # ---------------------------------------------------------
            # Coordinate labels -- every 18 points.
            #
            # X coordinates are shown along both the top and bottom.
            # Y coordinates are shown along both the left and right.
            # ---------------------------------------------------------

            # X labels -- top and bottom.
            x = MAJOR_SPACING

            while x < width:
                label = str(int(x))

                # Top edge.
                page.insert_text(
                    pymupdf.Point(x + 2, 10),
                    label,
                    fontsize=LABEL_FONT_SIZE,
                )

                # Bottom edge.
                page.insert_text(
                    pymupdf.Point(x + 2, height - 3),
                    label,
                    fontsize=LABEL_FONT_SIZE,
                )

                x += MAJOR_SPACING


            # Y labels -- left and right.
            y = MAJOR_SPACING

            while y < height:
                label = str(int(y))

                # Left edge.
                page.insert_text(
                    pymupdf.Point(2, y - 2),
                    label,
                    fontsize=LABEL_FONT_SIZE,
                )

                # Right edge.
                #
                # Leave enough room for a three-digit coordinate.
                page.insert_text(
                    pymupdf.Point(width - 22, y - 2),
                    label,
                    fontsize=LABEL_FONT_SIZE,
                )

                y += MAJOR_SPACING

            # ---------------------------------------------------------
            # Minor 3-point tick marks.
            #
            # Accumulate all tick marks in one Shape and commit them
            # together.  Calling page.draw_line() for every individual
            # tick causes PyMuPDF to repeatedly wrap and rescan the
            # page's content stream and becomes extremely slow.
            # ---------------------------------------------------------

            ticks = page.new_shape()

            # Ticks along vertical major grid lines.
            x = 0
            while x <= width:
                y_tick = MINOR_SPACING

                while y_tick < height:
                    if int(y_tick) % MAJOR_SPACING != 0:
                        ticks.draw_line(
                            pymupdf.Point(x, y_tick),
                            pymupdf.Point(
                                min(x + TICK_LENGTH, width),
                                y_tick,
                            ),
                        )
                    y_tick += MINOR_SPACING
                x += MAJOR_SPACING

            # Ticks along horizontal major grid lines.
            y = 0
            while y <= height:
                x_tick = MINOR_SPACING

                while x_tick < width:
                    if int(x_tick) % MAJOR_SPACING != 0:
                        ticks.draw_line(
                            pymupdf.Point(x_tick, y),
                            pymupdf.Point(
                                x_tick,
                                min(y + TICK_LENGTH, height),
                            ),
                        )
                    x_tick += MINOR_SPACING
                y += MAJOR_SPACING


                # Apply the drawing properties once and commit all ticks
                # to the page in a single operation.
                ticks.finish(width=TICK_WIDTH)
                ticks.commit()


        if output_path.exists():
            output_path.unlink()

        doc.save(
            output_path,
            garbage=4,
            deflate=True,
        )

    finally:
        doc.close()



def main() -> int:
    """
    This program gives us four useful behaviors

        pdf_coordinate_grid
    pdf_coordinate_grid --help
    pdf_coordinate_grid --version
    pdf_coordinate_grid SCCO.ICS213.pdf
    """
    parser = argparse.ArgumentParser(
        prog="pdf_coordinate_grid",
        description=(
            "Create a PDF coordinate grid for developing "
            "OutpostX .opxform form definitions."
        ),
    )

    parser.add_argument(
        "input_pdf",
        nargs="?",
        help="PDF file on which to overlay the coordinate grid.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )

    args = parser.parse_args()

    # With no arguments, display help rather than silently exiting.
    if not args.input_pdf:
        parser.print_help()
        return 0

    input_path = Path(args.input_pdf).expanduser().resolve()

    if not input_path.exists():
        print(f"PDF not found: {input_path}")
        return 1

    if input_path.suffix.lower() != ".pdf":
        print(f"Input file is not a PDF: {input_path}")
        return 1

    output_path = input_path.with_name(
        f"{input_path.stem}-grid.pdf"
    )

    try:
        create_coordinate_grid(input_path, output_path)
    except Exception as exc:
        print(f"Unable to create coordinate grid: {exc}")
        return 1

    print(f"Coordinate grid created: {output_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())