"""Claude-backed assistant provider (optional).

Activates only when an API key is configured (constructor argument or the
``ANTHROPIC_API_KEY`` environment variable) *and* the official ``anthropic``
SDK is installed. Absent either, ``is_available()`` returns False and the
application falls back to the offline analyst — the feature degrades cleanly,
never crashes.

The system prompt hard-codes the honesty contract (ADR-0004/0009): the model
may only reason from the supplied facts and hypotheses, must never invent
offsets or values, must separate facts from interpretation, and must answer in
French. The call is wrapped so any SDK/network error surfaces as a clean
message rather than an exception bubbling into the UI.
"""

from __future__ import annotations

import logging
import os

from calforge.ai.base import (
    AiRequest,
    AiTask,
    AssistantAnswer,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Tu es un assistant intégré à un logiciel professionnel de calibration ECU.
Règles absolues et non négociables :
- Tu ne raisonnes QUE sur les faits et hypothèses fournis dans le message.
- Tu n'inventes JAMAIS d'offset, de valeur, de dimension ou d'information
  absente du contexte. Si une information manque, dis-le explicitement.
- Tu distingues toujours clairement les faits avérés des hypothèses.
- Une hypothèse n'est jamais présentée comme une certitude ; rappelle son
  niveau de confiance quand tu t'y appuies.
- Tu réponds en français, de façon concise et professionnelle.
- La validation finale revient toujours au calibrateur humain.
"""

_TASK_INSTRUCTIONS = {
    AiTask.SUMMARIZE: "Rédige une synthèse claire et hiérarchisée du sujet.",
    AiTask.EXPLAIN: "Explique le sujet et le raisonnement derrière les hypothèses.",
    AiTask.COMPARE: "Analyse les différences et leur portée probable.",
    AiTask.PROPOSE: "Propose des pistes de travail prudentes et justifiées.",
    AiTask.ASK: "Réponds à la question de l'utilisateur.",
}


class AnthropicProvider:
    name = "anthropic"
    label = "Assistant IA (Claude)"

    def __init__(self, model: str, api_key: str = "", max_tokens: int = 1024) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def generate(self, request: AiRequest) -> AssistantAnswer:
        if not self.is_available():
            raise ProviderUnavailableError(
                "L'assistant IA (Claude) n'est pas configuré : clé API absente "
                "ou SDK « anthropic » non installé."
            )
        import anthropic

        instruction = _TASK_INSTRUCTIONS.get(request.task, _TASK_INSTRUCTIONS[AiTask.ASK])
        user_content = f"{instruction}\n\n{request.context.to_prompt()}"
        if request.question:
            user_content += f"\n\nQuestion de l'utilisateur : {request.question}"

        client = anthropic.Anthropic(api_key=self._api_key)
        try:
            message = client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            text = "".join(
                block.text for block in message.content if getattr(block, "type", "") == "text"
            )
        except Exception as exc:  # network, auth, rate limit…
            logger.exception("Anthropic request failed")
            raise ProviderUnavailableError(f"Appel à Claude échoué : {exc}") from exc

        return AssistantAnswer(
            provider=self.name,
            task=request.task,
            text=text.strip() or "(réponse vide)",
            facts_used=request.context.facts,
            hypotheses=request.context.hypotheses,
            confidence=None,
            ai_generated=True,
            extra_notes=(f"Modèle : {self._model}",),
        )
