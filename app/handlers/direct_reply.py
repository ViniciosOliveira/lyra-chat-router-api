from app.googlechat.schemas import NormalizedChatEvent


def build_direct_reply(event: NormalizedChatEvent) -> dict:
    if not event.text:
        return {"text": "Recebi o evento, mas não encontrei texto para analisar."}
    return {"text": "Consigo ajudar com análises e relatórios de Mkt Performance. Me mande a métrica, período e fonte."}
