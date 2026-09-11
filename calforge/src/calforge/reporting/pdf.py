"""HTML → PDF rendering using Qt only (no extra dependency).

``QTextDocument`` understands a rich-text subset of HTML/CSS; the report
templates in ``reporting.documents`` stay within it so the PDF matches the
browser view. Requires a running ``QGuiApplication`` (the app always has one;
tests create one). Import is Qt-bound, so this module is only imported from the
UI or from tests that own a Qt application.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument


def html_to_pdf(html: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    writer = QPdfWriter(str(target))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    writer.setResolution(96)

    document = QTextDocument()
    document.setHtml(html)
    # Match the text layout width to the printable page width so wrapping and
    # page breaks are computed correctly.
    page = writer.pageLayout().paintRectPixels(writer.resolution())
    document.setPageSize(QSizeF(page.width(), page.height()))
    document.print_(writer)
    return target
