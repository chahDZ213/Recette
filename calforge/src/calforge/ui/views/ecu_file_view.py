"""Per-file analysis view: hex table + annotations + map candidates.

Opened as a closable tab in the central area. All slow work (content read,
map detection) runs on the thread pool; the view refreshes itself after its
own actions, so it needs no global event routing.
"""

from __future__ import annotations

import logging

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from calforge.app import ApplicationContext
from calforge.data.models import AnnotationKind, MapCandidateStatus
from calforge.services.dto import (
    AnnotationInput,
    EcuFileDto,
    MapCandidateDto,
    MapDefinitionDto,
)
from calforge.ui.dialogs import show_error
from calforge.ui.models import (
    AnnotationTableModel,
    HexTableModel,
    MapCandidateTableModel,
)
from calforge.ui.theme import HIGHLIGHTS, PALETTE
from calforge.ui.workers import run_in_background

logger = logging.getLogger(__name__)


class AnnotationDialog(QDialog):
    """Create an annotation/bookmark for a byte range."""

    def __init__(self, offset: int, length: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Annoter la plage")
        self.setMinimumWidth(420)
        self._offset = offset
        self._length = length
        self._result: tuple[str, str, AnnotationKind] | None = None

        info = QLabel(f"Plage : 0x{offset:X} – 0x{offset + length:X} ({length} octet(s))")
        self._title = QLineEdit()
        self._comment = QTextEdit()
        self._comment.setAcceptRichText(False)
        self._bookmark = QCheckBox("Marquer comme favori de navigation")
        self._error = QLabel()
        self._error.setStyleSheet(f"color: {PALETTE['danger']};")
        self._error.hide()

        form = QFormLayout()
        form.addRow("Titre *", self._title)
        form.addRow("Commentaire", self._comment)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addLayout(form)
        layout.addWidget(self._bookmark)
        layout.addWidget(self._error)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        title = self._title.text().strip()
        if not title:
            self._error.setText("Le titre est obligatoire.")
            self._error.show()
            return
        kind = (
            AnnotationKind.BOOKMARK if self._bookmark.isChecked() else AnnotationKind.ANNOTATION
        )
        self._result = (title, self._comment.toPlainText(), kind)
        self.accept()

    def result_tuple(self) -> tuple[str, str, AnnotationKind] | None:
        return self._result


class Map2DDialog(QDialog):
    """Editable 2D map view.

    Cells hold **raw** values (exactly what is written to the binary), so
    edits are unambiguous and safe. When a definition provides a factor, the
    physical value is shown in each cell's tooltip. Editing tools:

    - type a new value directly into any cell,
    - select a region (or all) and apply a percentage change (+X %),

    and save the result as a NEW modified file — the original is never
    altered (ADR-0003). Passing ``context`` enables editing; without it the
    view is read-only.
    """

    #: Emitted with the new EcuFileDto after a successful "save as new file".
    file_created = Signal(object)

    def __init__(
        self,
        candidate: MapCandidateDto,
        values: np.ndarray,
        parent: QWidget | None = None,
        definition: MapDefinitionDto | None = None,
        context: ApplicationContext | None = None,
    ) -> None:
        super().__init__(parent)
        self._candidate = candidate
        self._definition = definition
        self._context = context
        self._editable = context is not None
        title = candidate.name or f"Candidat 0x{candidate.offset:X}"
        self.setWindowTitle(("Éditeur 2D — " if self._editable else "Vue 2D — ") + title)
        self.resize(min(1150, 120 + 66 * candidate.cols), min(780, 260 + 26 * candidate.rows))

        unit_note = ""
        if definition is not None and (definition.factor != 1.0 or definition.value_offset != 0.0):
            unit_note = (
                f" · unité physique <b>{definition.unit or '?'}</b> = brut × "
                f"{definition.factor:g} + {definition.value_offset:g} (édition en brut)"
            )
        elif definition is not None and definition.unit:
            unit_note = f" · unité : <b>{definition.unit}</b>"

        header = QLabel(
            f"<b>{title}</b> · {candidate.shape_label} · offset 0x{candidate.offset:X}"
            f"{unit_note}<br>"
            f"<span style='color:{PALETTE['text_dim']};'>Confiance {candidate.confidence:.0%} — "
            f"{candidate.rationale}</span>"
        )
        header.setWordWrap(True)

        self._table = QTableWidget(candidate.rows, candidate.cols)
        trigger = (
            QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.AnyKeyPressed
            if self._editable
            else QTableWidget.EditTrigger.NoEditTriggers
        )
        self._table.setEditTriggers(trigger)
        self._table.setHorizontalHeaderLabels([str(c) for c in range(candidate.cols)])
        self._table.setVerticalHeaderLabels([str(r) for r in range(candidate.rows)])
        for row in range(candidate.rows):
            for col in range(candidate.cols):
                item = QTableWidgetItem()
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row, col, item)
                self._set_cell(row, col, int(values[row, col]))
        self._recolor()
        self._table.resizeColumnsToContents()
        self._table.itemChanged.connect(lambda _i: self._recolor())

        layout = QVBoxLayout(self)
        layout.addWidget(header)

        if self._editable:
            tools = QHBoxLayout()
            tools.addWidget(QLabel("Modifier de"))
            self._percent = QDoubleSpinBox()
            self._percent.setRange(-95.0, 500.0)
            self._percent.setValue(10.0)
            self._percent.setSuffix(" %")
            self._percent.setDecimals(1)
            tools.addWidget(self._percent)
            apply_sel = QPushButton("Appliquer à la sélection")
            apply_sel.clicked.connect(lambda: self._apply_percent(selection_only=True))
            apply_all = QPushButton("Appliquer à toute la carte")
            apply_all.clicked.connect(lambda: self._apply_percent(selection_only=False))
            tools.addWidget(apply_sel)
            tools.addWidget(apply_all)
            tools.addStretch()
            layout.addLayout(tools)

        layout.addWidget(self._table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Fermer")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        if self._editable:
            save = QPushButton("Enregistrer comme nouveau fichier…")
            save.setDefault(True)
            save.clicked.connect(self._save_as_new_file)
            buttons.addButton(save, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.clicked.connect(
            lambda b: self.reject() if buttons.buttonRole(b) == QDialogButtonBox.ButtonRole.RejectRole else None
        )
        layout.addWidget(buttons)

    # ---------------------------------------------------------- cell I/O ----

    def _max_value(self) -> int:
        return 0xFFFF if self._candidate.element_size == 2 else 0xFF

    def _set_cell(self, row: int, col: int, raw: int) -> None:
        item = self._table.item(row, col)
        item.setText(str(raw))
        if self._definition and (self._definition.factor != 1.0 or self._definition.value_offset != 0.0):
            physical = raw * self._definition.factor + self._definition.value_offset
            item.setToolTip(f"physique : {physical:.2f} {self._definition.unit}")

    def _cell_value(self, row: int, col: int) -> int:
        try:
            return int(round(float(self._table.item(row, col).text())))
        except (ValueError, AttributeError):
            return 0

    def current_values(self) -> np.ndarray:
        rows, cols = self._candidate.rows, self._candidate.cols
        return np.array(
            [[self._cell_value(r, c) for c in range(cols)] for r in range(rows)],
            dtype=np.int64,
        )

    def _recolor(self) -> None:
        values = self.current_values().astype(np.float64)
        low, high = float(values.min()), float(values.max())
        span = (high - low) or 1.0
        cold, hot = QColor("#2b5db8"), QColor(PALETTE["danger"])
        for row in range(self._candidate.rows):
            for col in range(self._candidate.cols):
                t = (float(values[row, col]) - low) / span
                self._table.item(row, col).setBackground(
                    QColor(
                        round(cold.red() + t * (hot.red() - cold.red())),
                        round(cold.green() + t * (hot.green() - cold.green())),
                        round(cold.blue() + t * (hot.blue() - cold.blue())),
                        160,
                    )
                )

    # ----------------------------------------------------------- editing ----

    def _apply_percent(self, *, selection_only: bool) -> None:
        factor = 1.0 + self._percent.value() / 100.0
        max_value = self._max_value()
        cells = (
            [(i.row(), i.column()) for i in self._table.selectedIndexes()]
            if selection_only
            else [
                (r, c)
                for r in range(self._candidate.rows)
                for c in range(self._candidate.cols)
            ]
        )
        if not cells:
            show_error(self, "Sélectionnez d'abord des cellules.")
            return
        self._table.blockSignals(True)
        for row, col in cells:
            new_raw = int(round(self._cell_value(row, col) * factor))
            self._set_cell(row, col, max(0, min(max_value, new_raw)))
        self._table.blockSignals(False)
        self._recolor()

    def _save_as_new_file(self) -> None:
        if self._context is None:
            return
        from PySide6.QtWidgets import QInputDialog

        parent_name = self._context.ecu_files.get(self._candidate.ecu_file_id).original_filename
        default = parent_name.rsplit(".", 1)
        suggested = f"{default[0]}_modifie" + (f".{default[1]}" if len(default) > 1 else "")
        name, accepted = QInputDialog.getText(
            self, "Enregistrer la modification", "Nom du nouveau fichier :", text=suggested
        )
        if not accepted:
            return
        try:
            new_file = self._context.analysis.edit_map(
                self._candidate.id, self.current_values(), output_filename=name.strip() or suggested
            )
        except Exception as exc:
            show_error(self, f"Enregistrement impossible : {exc}")
            return
        logger.info("Map edit saved as file #%d", new_file.id)
        self.file_created.emit(new_file)
        self.accept()


class EcuFileView(QWidget):
    #: Emitted with a new EcuFileDto to ask the host to open it in a tab.
    file_open_requested = Signal(object)

    def __init__(
        self, context: ApplicationContext, file: EcuFileDto, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._file = file
        self._data = b""

        # -- toolbar ---------------------------------------------------------
        self._goto = QLineEdit()
        self._goto.setPlaceholderText("Aller à l'offset (hex)")
        self._goto.setMaximumWidth(180)
        self._goto.returnPressed.connect(self._on_goto)

        annotate_button = QPushButton("Annoter la sélection…")
        annotate_button.clicked.connect(self._annotate_selection)
        detect_button = QPushButton("Détecter les cartographies")
        detect_button.clicked.connect(self._detect_maps)
        self._detect_button = detect_button
        apply_button = QPushButton("Appliquer les définitions")
        apply_button.setToolTip(
            "Applique les packs de définitions correspondant à ce fichier "
            "(empreinte, signature ou taille)"
        )
        apply_button.clicked.connect(self._apply_definitions)
        self._apply_button = apply_button
        self._status = QLabel()

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._goto)
        toolbar.addWidget(annotate_button)
        toolbar.addWidget(detect_button)
        toolbar.addWidget(apply_button)
        toolbar.addWidget(self._status)
        toolbar.addStretch()

        # -- hex table -------------------------------------------------------
        self._hex_model = HexTableModel()
        self._hex_table = QTableView()
        self._hex_table.setModel(self._hex_model)
        self._hex_table.horizontalHeader().setDefaultSectionSize(32)
        self._hex_table.horizontalHeader().setStretchLastSection(True)
        self._hex_table.verticalHeader().setDefaultSectionSize(22)

        # -- side panel ------------------------------------------------------
        self._annotation_model = AnnotationTableModel()
        self._annotation_table = QTableView()
        self._annotation_table.setModel(self._annotation_model)
        self._annotation_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._annotation_table.horizontalHeader().setStretchLastSection(True)
        self._annotation_table.verticalHeader().setVisible(False)
        self._annotation_table.doubleClicked.connect(self._jump_to_annotation)

        delete_annotation = QPushButton("Supprimer l'annotation")
        delete_annotation.clicked.connect(self._delete_annotation)

        self._candidate_model = MapCandidateTableModel()
        self._candidate_table = QTableView()
        self._candidate_table.setModel(self._candidate_model)
        self._candidate_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._candidate_table.horizontalHeader().setStretchLastSection(True)
        self._candidate_table.verticalHeader().setVisible(False)
        self._candidate_table.doubleClicked.connect(self._jump_to_candidate)

        validate_button = QPushButton("Valider…")
        validate_button.clicked.connect(self._validate_candidate)
        reject_button = QPushButton("Rejeter")
        reject_button.clicked.connect(self._reject_candidate)
        view2d_button = QPushButton("Vue 2D")
        view2d_button.clicked.connect(self._open_2d)

        candidate_buttons = QHBoxLayout()
        for button in (validate_button, reject_button, view2d_button):
            candidate_buttons.addWidget(button)
        candidate_buttons.addStretch()

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.addWidget(QLabel("<b>Annotations & favoris</b>"))
        side_layout.addWidget(self._annotation_table)
        side_layout.addWidget(delete_annotation)
        side_layout.addWidget(QLabel("<b>Cartographies (hypothèses à valider)</b>"))
        side_layout.addWidget(self._candidate_table)
        side_layout.addLayout(candidate_buttons)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._hex_table)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 3)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addLayout(toolbar)
        layout.addWidget(splitter)

        self._load_content()
        self._refresh_side_panels()

    @property
    def ecu_file(self) -> EcuFileDto:
        return self._file

    # ------------------------------------------------------------- loading --

    def _load_content(self) -> None:
        service = self._context.ecu_files
        file_id = self._file.id
        self._status.setText("Chargement…")

        def on_done(data: object) -> None:
            assert isinstance(data, bytes)
            self._data = data
            self._hex_model.set_data(data)
            self._status.setText("")
            self._apply_highlights()

        run_in_background(
            lambda: service.read_content(file_id),
            on_done=on_done,
            on_error=lambda message: show_error(self, f"Lecture échouée : {message}"),
        )

    def _refresh_side_panels(self) -> None:
        self._annotation_model.set_items(
            self._context.annotations.list_for_file(self._file.id)
        )
        self._candidate_model.set_items(
            self._context.analysis.list_candidates(self._file.id)
        )
        self._apply_highlights()

    def _apply_highlights(self) -> None:
        highlights: list[tuple[int, int, object]] = []
        for annotation in self._annotation_model.items():
            key = "bookmark" if annotation.kind == AnnotationKind.BOOKMARK else "annotation"
            highlights.append((annotation.offset, annotation.end, HIGHLIGHTS[key]()))
        for candidate in self._candidate_model.items():
            if candidate.status == MapCandidateStatus.REJECTED:
                continue
            key = (
                "candidate_validated"
                if candidate.status == MapCandidateStatus.VALIDATED
                else "candidate"
            )
            highlights.append((candidate.offset, candidate.end, HIGHLIGHTS[key]()))
        self._hex_model.set_highlights(highlights)

    # ---------------------------------------------------------- navigation --

    def _on_goto(self) -> None:
        text = self._goto.text().strip().removeprefix("0x").removeprefix("0X")
        try:
            offset = int(text, 16)
        except ValueError:
            show_error(self, f"Offset hexadécimal invalide : {self._goto.text()!r}")
            return
        self._scroll_to(offset)

    def _scroll_to(self, offset: int) -> None:
        if not self._data:
            return
        offset = max(0, min(offset, len(self._data) - 1))
        index = self._hex_model.index_for_offset(offset)
        self._hex_table.scrollTo(index, QTableView.ScrollHint.PositionAtCenter)
        self._hex_table.setCurrentIndex(index)

    def _jump_to_annotation(self, index) -> None:
        annotation = self._annotation_model.item_at(index.row())
        if annotation is not None:
            self._scroll_to(annotation.offset)

    def _jump_to_candidate(self, index) -> None:
        candidate = self._candidate_model.item_at(index.row())
        if candidate is not None:
            self._scroll_to(candidate.offset)

    # --------------------------------------------------------- annotations --

    def _selection_range(self) -> tuple[int, int] | None:
        """(offset, length) covered by the hex selection, byte columns only."""
        indexes = [
            i
            for i in self._hex_table.selectionModel().selectedIndexes()
            if i.column() < HexTableModel.BYTES_PER_ROW
        ]
        offsets = [
            i.row() * HexTableModel.BYTES_PER_ROW + i.column()
            for i in indexes
            if i.row() * HexTableModel.BYTES_PER_ROW + i.column() < len(self._data)
        ]
        if not offsets:
            return None
        start, end = min(offsets), max(offsets) + 1
        return start, end - start

    def _annotate_selection(self) -> None:
        selection = self._selection_range()
        if selection is None:
            QMessageBox.information(
                self, "Annotation", "Sélectionnez d'abord des octets dans la vue hexadécimale."
            )
            return
        offset, length = selection
        dialog = AnnotationDialog(offset, length, self)
        if not dialog.exec() or dialog.result_tuple() is None:
            return
        title, comment, kind = dialog.result_tuple()
        try:
            self._context.annotations.add(
                AnnotationInput(
                    ecu_file_id=self._file.id,
                    offset=offset,
                    length=length,
                    kind=kind,
                    title=title,
                    comment=comment,
                )
            )
        except Exception as exc:
            show_error(self, f"Annotation impossible : {exc}")
            return
        self._refresh_side_panels()

    def _delete_annotation(self) -> None:
        index = self._annotation_table.currentIndex()
        annotation = self._annotation_model.item_at(index.row()) if index.isValid() else None
        if annotation is None:
            return
        self._context.annotations.delete(annotation.id)
        self._refresh_side_panels()

    # ----------------------------------------------------------- detection --

    def _detect_maps(self) -> None:
        service = self._context.analysis
        file_id = self._file.id
        self._detect_button.setEnabled(False)
        self._status.setText("Détection en cours…")

        def on_done(candidates: object) -> None:
            self._detect_button.setEnabled(True)
            count = len(candidates)  # type: ignore[arg-type]
            self._status.setText(f"{count} candidat(s) proposé(s)")
            self._refresh_side_panels()

        def on_error(message: str) -> None:
            self._detect_button.setEnabled(True)
            self._status.setText("")
            show_error(self, f"Détection échouée : {message}")

        run_in_background(lambda: service.detect_maps(file_id), on_done, on_error)

    def _apply_definitions(self) -> None:
        service = self._context.definitions
        file_id = self._file.id
        self._apply_button.setEnabled(False)
        self._status.setText("Application des définitions…")

        def on_done(candidates: object) -> None:
            self._apply_button.setEnabled(True)
            applied = [c for c in candidates if c.definition_id is not None]  # type: ignore[union-attr]
            if applied:
                self._status.setText(f"{len(applied)} définition(s) appliquée(s)")
            else:
                self._status.setText("Aucun pack ne correspond à ce fichier")
            self._refresh_side_panels()

        def on_error(message: str) -> None:
            self._apply_button.setEnabled(True)
            self._status.setText("")
            show_error(self, f"Application échouée : {message}")

        run_in_background(lambda: service.apply_definitions(file_id), on_done, on_error)

    def _selected_candidate(self) -> MapCandidateDto | None:
        index = self._candidate_table.currentIndex()
        return self._candidate_model.item_at(index.row()) if index.isValid() else None

    def _validate_candidate(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None:
            return
        from PySide6.QtWidgets import QInputDialog

        name, accepted = QInputDialog.getText(
            self,
            "Valider la cartographie",
            "Nom de la cartographie (ex. « Injection — charge/régime ») :",
            text=candidate.name,
        )
        if not accepted:
            return
        self._context.analysis.set_candidate_status(
            candidate.id, MapCandidateStatus.VALIDATED, name=name
        )
        self._refresh_side_panels()

    def _reject_candidate(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None:
            return
        self._context.analysis.set_candidate_status(candidate.id, MapCandidateStatus.REJECTED)
        self._refresh_side_panels()

    def _open_2d(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None:
            return
        analysis = self._context.analysis
        definitions = self._context.definitions

        def work() -> tuple[np.ndarray, MapDefinitionDto | None]:
            values = analysis.read_map_values(candidate.id)
            definition = (
                definitions.get_definition(candidate.definition_id)
                if candidate.definition_id is not None
                else None
            )
            return values, definition

        def on_done(payload: object) -> None:
            values, definition = payload  # type: ignore[misc]
            dialog = Map2DDialog(
                candidate, values, self, definition=definition, context=self._context
            )
            dialog.file_created.connect(self._on_map_edited)
            dialog.exec()

        run_in_background(
            work,
            on_done=on_done,
            on_error=lambda message: show_error(self, f"Décodage échoué : {message}"),
        )

    def _on_map_edited(self, new_file: object) -> None:
        assert isinstance(new_file, EcuFileDto)
        self.file_open_requested.emit(new_file)
