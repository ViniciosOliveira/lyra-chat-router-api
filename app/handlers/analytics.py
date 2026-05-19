from app.googlechat.schemas import NormalizedChatEvent
from app.policies.engine import PolicyDecision


def build_analytics_response(event: NormalizedChatEvent, decision: PolicyDecision) -> dict:
    return {
        "text": (
            "Análise registrada dentro do escopo permitido. "
            f"Intent detectada: {decision.intent.value}. "
            "Na próxima fase eu conecto isso às fontes reais de dados."
        )
    }
