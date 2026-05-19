from app.googlechat.schemas import NormalizedChatEvent


def normalize_event(payload: dict) -> NormalizedChatEvent:
    event_type = payload.get("type") or payload.get("eventType") or "UNKNOWN"
    space = payload.get("space") or {}
    user = payload.get("user") or payload.get("message", {}).get("sender") or {}
    message = payload.get("message") or {}
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
