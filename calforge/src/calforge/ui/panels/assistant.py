"""AI assistant dock.

Context-aware: it targets whatever the user is looking at — the selected
vehicle, or the ECU file of the active analysis tab — and offers quick actions
plus a free-text box. Every answer renders with its provider, the facts it
used, the hypotheses it relied on, and a standing disclaimer; results can be
saved to the vehicle timeline (the human-validation/documentation path).

All provider calls run on a worker thread; the panel never blocks the UI.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from html import escape

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from calforge.ai.base import AssistantAnswer
from calforge.app import ApplicationContext
from calforge.data.models import HistoryEntryType
from calforge.services.dto import EcuFileDto, HistoryEntryInput, VehicleDto
from calforge.ui.dialogs import show_error
from calforge.ui.theme import PALETTE
from calforge.ui.workers import run_in_background

logger = logging.getLogger(__name__)


class AssistantPanel(QWidget):
    def __init__(self, context: ApplicationContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._vehicle: VehicleDto | None = None
        self._file: EcuFileDto | None = None
        self._last_answer: AssistantAnswer | None = None
        self._busy = False

        self._target = QLabel()
        self._target.setWordWrap(True)

        self._provider = QComboBox()
        self._reload_providers()

        self._summarize_file_btn = QPushButton("Résumer le fichier")
        self._summarize_file_btn.clicked.connect(self._summarize_file)
        self._propose_btn = QPushButton("Proposer des pistes")
        self._propose_btn.clicked.connect(self._propose)
        self._summarize_vehicle_btn = QPushButton("Résumer le véhicule")
        self._summarize_vehicle_btn.clicked.connect(self._summarize_vehicle)

        actions = QHBoxLayout()
        for button in (
            self._summarize_file_btn,
            self._propose_btn,
            self._summarize_vehicle_btn,
        ):
            actions.addWidget(button)
        actions.addStretch()

        provider_row = QHBoxLayout()
        provider_row.addWidget(QLabel("Assistant :"))
        provider_row.addWidget(self._provider)
        provider_row.addStretch()

        self._output = QTextBrowser()
        self._output.setOpenExternalLinks(False)
        self._render_placeholder()

        self._question = QLineEdit()
        self._question.setPlaceholderText("Poser une question sur la cible sélectionnée…")
        self._question.returnPressed.connect(self._ask)
        ask_button = QPushButton("Demander")
        ask_button.clicked.connect(self._ask)

        self._save_button = QPushButton("Enregistrer dans l'historique du véhicule")
        self._save_button.clicked.connect(self._save_answer)
        self._save_button.setEnabled(False)

        ask_row = QHBoxLayout()
        ask_row.addWidget(self._question)
        ask_row.addWidget(ask_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._target)
        layout.addLayout(provider_row)
        layout.addLayout(actions)
        layout.addWidget(self._output, stretch=1)
        layout.addLayout(ask_row)
        layout.addWidget(self._save_button)
        self._update_enabled()

    # -------------------------------------------------------------- state --

    def set_vehicle(self, vehicle: VehicleDto | None) -> None:
        self._vehicle = vehicle
        self._update_target_label()
        self._update_enabled()

    def set_active_file(self, file: EcuFileDto | None) -> None:
        self._file = file
        self._update_target_label()
        self._update_enabled()

    def _update_target_label(self) -> None:
        parts = []
        if self._file is not None:
            parts.append(f"Fichier : <b>{escape(self._file.original_filename)}</b>")
        if self._vehicle is not None:
            parts.append(f"Véhicule : <b>{escape(self._vehicle.display_name)}</b>")
        self._target.setText(
            "Cible — " + " · ".join(parts) if parts else
            "<i>Aucune cible : sélectionnez un véhicule ou ouvrez un fichier.</i>"
        )

    def _reload_providers(self) -> None:
        self._provider.clear()
        for name, label in self._context.assistant.available_providers():
            self._provider.addItem(label, name)
        if self._provider.count() == 0:
            self._provider.addItem("Analyse locale (hors-ligne)", "offline")

    def _current_provider(self) -> str:
        return self._provider.currentData() or "offline"

    def _update_enabled(self) -> None:
        has_file = self._file is not None and not self._busy
        has_vehicle = self._vehicle is not None and not self._busy
        self._summarize_file_btn.setEnabled(has_file)
        self._propose_btn.setEnabled(has_file)
        self._summarize_vehicle_btn.setEnabled(has_vehicle)
        self._question.setEnabled(has_file or has_vehicle)

    # ------------------------------------------------------------ actions --

    def _summarize_file(self) -> None:
        if self._file is not None:
            file_id = self._file.id
            provider = self._current_provider()
            self._run(lambda: self._context.assistant.summarize_file(file_id, provider=provider))

    def _propose(self) -> None:
        if self._file is not None:
            file_id = self._file.id
            provider = self._current_provider()
            self._run(lambda: self._context.assistant.propose_for_file(file_id, provider=provider))

    def _summarize_vehicle(self) -> None:
        if self._vehicle is not None:
            vehicle_id = self._vehicle.id
            provider = self._current_provider()
            self._run(
                lambda: self._context.assistant.summarize_vehicle(vehicle_id, provider=provider)
            )

    def _ask(self) -> None:
        question = self._question.text().strip()
        if not question:
            return
        provider = self._current_provider()
        if self._file is not None:
            file_id = self._file.id
            self._run(
                lambda: self._context.assistant.ask_about_file(
                    file_id, question, provider=provider
                )
            )
        elif self._vehicle is not None:
            vehicle_id = self._vehicle.id
            self._run(
                lambda: self._context.assistant.ask_about_vehicle(
                    vehicle_id, question, provider=provider
                )
            )

    def _run(self, operation) -> None:
        self._busy = True
        self._update_enabled()
        self._output.setHtml(
            f"<p style='color:{PALETTE['text_dim']};'>Analyse en cours…</p>"
        )

        def on_done(answer: object) -> None:
            self._busy = False
            self._update_enabled()
            assert isinstance(answer, AssistantAnswer)
            self._last_answer = answer
            self._save_button.setEnabled(self._vehicle is not None)
            self._render_answer(answer)

        def on_error(message: str) -> None:
            self._busy = False
            self._update_enabled()
            show_error(self, f"Assistant indisponible : {message}")

        run_in_background(operation, on_done, on_error)

    # ------------------------------------------------------------ render --

    def _render_placeholder(self) -> None:
        self._output.setHtml(
            f"<p style='color:{PALETTE['text_dim']};'>"
            "L'assistant analyse vos données <b>sans jamais inventer d'information</b> : "
            "il distingue toujours les faits mesurés des hypothèses, affiche son niveau "
            "de confiance et vous laisse la validation finale.</p>"
        )

    def _render_answer(self, answer: AssistantAnswer) -> None:
        accent = PALETTE["accent"]
        dim = PALETTE["text_dim"]
        warning = PALETTE["warning"]
        html = [
            f"<div style='color:{accent};font-weight:bold;'>{escape(answer.provider)}"
            f" · {escape(answer.task.value)}</div>",
            f"<p style='white-space:pre-wrap;'>{escape(answer.text)}</p>",
        ]
        if answer.hypotheses:
            html.append(f"<div style='color:{warning};font-weight:bold;'>Hypothèses utilisées</div>")
            html.append("<ul>")
            for hypothesis in answer.hypotheses:
                html.append(
                    f"<li>{escape(hypothesis.statement)} "
                    f"<span style='color:{dim};'>(confiance {hypothesis.confidence:.0%})</span></li>"
                )
            html.append("</ul>")
        if answer.facts_used:
            html.append(
                f"<div style='color:{dim};'>Basé sur {len(answer.facts_used)} fait(s) du projet.</div>"
            )
        html.append(
            f"<p style='color:{dim};font-style:italic;margin-top:8px;'>"
            f"{escape(answer.disclaimer())}</p>"
        )
        self._output.setHtml("".join(html))

    def _save_answer(self) -> None:
        if self._last_answer is None or self._vehicle is None:
            return
        title = f"Assistant ({self._last_answer.provider}) — {self._last_answer.task.value}"
        try:
            self._context.history.add(
                HistoryEntryInput(
                    vehicle_id=self._vehicle.id,
                    entry_type=HistoryEntryType.NOTE,
                    title=title[:200],
                    content=self._last_answer.text + "\n\n" + self._last_answer.disclaimer(),
                    occurred_at=datetime.now(UTC),
                )
            )
        except Exception as exc:
            show_error(self, f"Enregistrement impossible : {exc}")
            return
        self._save_button.setEnabled(False)
        self._output.append(
            f"<p style='color:{PALETTE['success']};'>✓ Enregistré dans l'historique du véhicule.</p>"
        )
