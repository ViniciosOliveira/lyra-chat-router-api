from app.googlechat.schemas import NormalizedChatEvent
from app.policies.engine import PolicyDecision


def build_scoped_operation_response(event: NormalizedChatEvent, decision: PolicyDecision) -> dict:
    if decision.scope == "turnstile_only":
        return {
            "text": (
                "Pedido de catraca reconhecido dentro do escopo permitido. "
                "Na troca global, este espaço já está mapeado no router; a execução física segue bloqueada "
                "até conectarmos o handler operacional oficial."
            )
        }
    if decision.scope == "certificates_correios_only":
        return {
            "text": (
                "Pedido reconhecido dentro do escopo de certificados/Correios. "
                "Na troca global, este espaço já está mapeado no router; a execução final depende do handler operacional oficial."
            )
        }
    return {"text": "Pedido reconhecido dentro do escopo configurado."}
