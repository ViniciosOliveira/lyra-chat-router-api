from app.policies.engine import PolicyDecision


SCOPED_DENY_TEXT = {
    "turnstile_only": (
        "Essa solicitação está fora do escopo permitido para este grupo. "
        "Posso ajudar apenas com operação de catraca aqui."
    ),
    "certificates_correios_only": (
        "Essa solicitação está fora do escopo permitido para este grupo. "
        "Posso ajudar apenas com certificados ou etiquetas dos Correios aqui."
    ),
    "marketing_performance_analysis_only": (
        "Essa solicitação está fora do escopo permitido para este grupo. "
        "Aqui eu posso fazer análises, diagnósticos, relatórios e recomendações; não executo mudanças operacionais."
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
