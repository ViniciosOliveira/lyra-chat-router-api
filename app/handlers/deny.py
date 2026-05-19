from app.policies.engine import PolicyDecision


def build_deny_response(decision: PolicyDecision) -> dict:
    return {
        "text": (
            "Neste grupo eu só posso fazer análises e relatórios. "
            "Alterações operacionais dependem de autorização explícita do Vinícios fora do fluxo comum."
        )
    }
