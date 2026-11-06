#!/usr/bin/env python3
"""Render the official 2022 English curriculum vocabulary appendix for OCR.

Source:
  Ministry of Education, PRC
  《义务教育英语课程标准（2022年版）》
  http://www.moe.gov.cn/srcsite/A26/s8001/202204/W020220420582349487953.pdf

The official Appendix 3 level-three list begins on printed page 98 and ends
before the irregular-verb list on printed page 133. The PDF is paginated seven
pages ahead of the printed page, so PDF pages 105 through 139 are rendered.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    document = fitz.open(args.pdf)
    if document.page_count < 139:
        raise SystemExit(f"Expected at least 139 PDF pages, got {document.page_count}")

    for pdf_page in range(105, 140):
        pixmap = document[pdf_page - 1].get_pixmap(
            matrix=fitz.Matrix(2.0, 2.0),
            alpha=False,
        )
        target = args.output / f"kebiao-p{pdf_page:03d}.png"
        pixmap.save(target)
        print(target)


if __name__ == "__main__":
    main()
