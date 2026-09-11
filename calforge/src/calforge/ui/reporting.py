"""UI glue for producing report files (PDF / HTML) off the GUI thread."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget

from calforge.reporting.pdf import html_to_pdf
from calforge.ui.dialogs import show_error
from calforge.ui.workers import run_in_background


def export_report(
    parent: QWidget,
    build_html,
    default_name: str,
    *,
    on_status=lambda message, timeout: None,
) -> None:
    """Ask for a target file then render the report there.

    ``build_html`` is a zero-arg callable run on a worker thread (it may hit
    services); PDF rendering also runs there. HTML output is written directly.
    """
    target, selected = QFileDialog.getSaveFileName(
        parent,
        "Enregistrer le rapport",
        default_name,
        "PDF (*.pdf);;Page HTML (*.html)",
    )
    if not target:
        return
    path = Path(target)
    as_pdf = path.suffix.lower() != ".html" and "html" not in selected.lower()

    def work() -> str:
        html = build_html()
        if as_pdf:
            final = path if path.suffix else path.with_suffix(".pdf")
            html_to_pdf(html, final)
            return str(final)
        final = path if path.suffix else path.with_suffix(".html")
        final.write_text(html, encoding="utf-8")
        return str(final)

    on_status("Génération du rapport…", 0)
    run_in_background(
        work,
        on_done=lambda saved: on_status(f"Rapport enregistré : {saved}", 6000),
        on_error=lambda message: show_error(parent, f"Génération échouée : {message}"),
    )
