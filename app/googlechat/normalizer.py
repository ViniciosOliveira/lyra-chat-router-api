from app.googlechat.schemas import NormalizedChatEvent


def normalize_event(payload: dict) -> NormalizedChatEvent:
    chat_payload = payload.get("chat") or {}
    message_payload = chat_payload.get("messagePayload") or {}
    message = payload.get("message") or message_payload.get("message") or {}
    space = payload.get("space") or message_payload.get("space") or message.get("space") or {}
    user = payload.get("user") or chat_payload.get("user") or message.get("sender") or {}
    event_type = (
        payload.get("type")
        or payload.get("eventType")
        or ("MESSAGE" if message_payload.get("message") else None)
        or "UNKNOWN"
    )
    thread = message.get("thread") or payload.get("thread") or {}

    return NormalizedChatEvent(
        event_type=event_type,
        space_name=space.get("name"),
        space_display_name=space.get("displayName"),
        user_name=user.get("name"),
        user_display_name=user.get("displayName"),
        user_email=user.get("email"),
        thread_name=thread.get("name"),
        message_name=message.get("name"),
        text=(message.get("text") or payload.get("text") or "").strip(),
        raw=payload,
    )
