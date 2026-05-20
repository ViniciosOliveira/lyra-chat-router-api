from app.policies.engine import PolicyDecision


SCOPED_DENY_TEXT = {
    "turnstile_only": (
        "Essa solicitação está fora do escopo permitido para este grupo. "
        "Vou verificar com o Vinícios antes de avançar."
    ),
    "certificates_correios_only": (
        "Essa solicitação está fora do escopo permitido para este grupo. "
        "Vou verificar com o Vinícios antes de avançar."
    ),
    "marketing_performance_analysis_only": (
        "Essa solicitação está fora do escopo permitido para este grupo. "
        "Vou verificar com o Vinícios antes de avançar."
    ),
}


def build_deny_response(decision: PolicyDecision) -> dict:
    if decision.reason == "User is not allowed for this Google Chat space":
        return {"text": "Você não está autorizado a acionar a Lyra neste espaço."}
    if decision.policy_key == "unknown_space":
        return {"text": "Este espaço ainda não está configurado na Lyra Chat Router API."}
    return {
        "text": SCOPED_DENY_TEXT.get(
            decision.scope,
            "Não posso executar esse pedido neste espaço.",
        )
    }
