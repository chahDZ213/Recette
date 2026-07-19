"""Offline analyst — the always-available, network-free assistant.

This is not a language model: it is a deterministic rule-based analyst that
composes the factual context into a readable briefing. It is honest by
construction — it only restates measured facts and already-scored hypotheses,
never inventing anything — and it makes the assistant genuinely useful with
zero configuration, while keeping the whole feature testable without a network.
"""

from __future__ import annotations

from calforge.ai.base import (
    AiRequest,
    AiTask,
    AssistantAnswer,
    ContextFact,
    ContextHypothesis,
)


def _bullet_facts(facts: tuple[ContextFact, ...]) -> str:
    return "\n".join(f"• {f.label} : {f.value}" for f in facts) or "• (aucun fait disponible)"


def _bullet_hypotheses(hypotheses: tuple[ContextHypothesis, ...]) -> str:
    if not hypotheses:
        return "• Aucune hypothèse en cours."
    return "\n".join(
        f"• {h.statement} — confiance {h.confidence:.0%}\n    ↳ {h.rationale}"
        for h in hypotheses
    )


class OfflineAnalyst:
    name = "offline"
    label = "Analyse locale (hors-ligne)"

    def is_available(self) -> bool:
        return True

    def generate(self, request: AiRequest) -> AssistantAnswer:
        context = request.context
        if request.task == AiTask.COMPARE:
            body = self._compare(request)
        elif request.task == AiTask.EXPLAIN:
            body = self._explain(request)
        elif request.task == AiTask.PROPOSE:
            body = self._propose(request)
        elif request.task == AiTask.ASK:
            body = self._ask(request)
        else:
            body = self._summarize(request)

        return AssistantAnswer(
            provider=self.name,
            task=request.task,
            text=body,
            facts_used=context.facts,
            hypotheses=context.hypotheses,
            confidence=None,  # a factual restatement, not a judgement
            ai_generated=False,
        )

    # ---------------------------------------------------------- renderers --

    def _summarize(self, request: AiRequest) -> str:
        c = request.context
        parts = [
            f"Synthèse de {c.subject}.",
            "",
            "Faits établis :",
            _bullet_facts(c.facts),
        ]
        if c.hypotheses:
            parts += ["", "Hypothèses à valider :", _bullet_hypotheses(c.hypotheses)]
        if c.notes:
            parts += ["", "Points notables :", "\n".join(f"• {n}" for n in c.notes)]
        return "\n".join(parts)

    def _explain(self, request: AiRequest) -> str:
        c = request.context
        parts = [f"Explication — {c.subject}.", "", _bullet_facts(c.facts)]
        if c.hypotheses:
            parts += [
                "",
                "Ce qui est supposé (et pourquoi) :",
                _bullet_hypotheses(c.hypotheses),
            ]
        return "\n".join(parts)

    def _compare(self, request: AiRequest) -> str:
        c = request.context
        parts = [f"{c.subject}.", "", _bullet_facts(c.facts)]
        if c.notes:
            parts += ["", "Détail des zones modifiées :", "\n".join(f"• {n}" for n in c.notes)]
            touched = [n for n in c.notes if "touche :" in n]
            if touched:
                parts += [
                    "",
                    f"{len(touched)} zone(s) de différence recoupent des "
                    "cartographies connues — à examiner en priorité.",
                ]
        return "\n".join(parts)

    def _propose(self, request: AiRequest) -> str:
        c = request.context
        suggestions = [
            "Valider ou rejeter les cartographies proposées avant toute analyse.",
            "Comparer ce fichier à son original pour isoler les zones travaillées.",
            "Annoter les zones sensibles (checksums, limiteurs) pour ne pas les perdre.",
        ]
        return "\n".join(
            [
                f"Pistes de travail pour {c.subject} :",
                "",
                "\n".join(f"• {s}" for s in suggestions),
                "",
                "Ces suggestions sont méthodologiques et génériques (analyse locale) ; "
                "elles ne reposent que sur les faits ci-dessous.",
                "",
                _bullet_facts(c.facts),
            ]
        )

    def _ask(self, request: AiRequest) -> str:
        c = request.context
        return "\n".join(
            [
                "L'analyse locale (hors-ligne) ne rédige pas de réponse libre : "
                "elle vous restitue les données pertinentes pour votre question.",
                f"\nQuestion : {request.question}" if request.question else "",
                "",
                f"Éléments connus sur {c.subject} :",
                _bullet_facts(c.facts),
                "" if not c.hypotheses else "\nHypothèses :\n" + _bullet_hypotheses(c.hypotheses),
                "\nPour une réponse rédigée, activez l'assistant IA (Claude) dans la "
                "configuration.",
            ]
        )
