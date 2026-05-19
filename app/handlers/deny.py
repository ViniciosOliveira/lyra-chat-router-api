from app.policies.engine import PolicyDecision


SCOPED_DENY_TEXT = {
    "turnstile_only": "Só posso ajudar com controle de catraca neste grupo.",
    "certificates_correios_only": "Só posso ajudar neste grupo com assinatura de certificados digitais e emissão de etiquetas dos Correios.",
    "marketing_performance_analysis_only": (
        "Neste grupo eu só posso fazer análises e relatórios. "
        "Alterações operacionais dependem de autorização explícita do Vinícios fora do fluxo comum."
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
