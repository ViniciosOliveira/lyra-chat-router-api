from app.googlechat.schemas import NormalizedChatEvent


def build_direct_reply(event: NormalizedChatEvent) -> dict:
    if not event.text:
        return {"text": "Recebi o evento, mas não encontrei texto para analisar."}
    return {
        "text": (
            "Mensagem recebida pela Lyra Chat Router API. "
            "Este espaço já está mapeado para a troca global; a próxima etapa é conectar o handler de execução/IA."
        )
    }
