from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NormalizedChatEvent:
    event_type: str
    space_name: str | None
    space_display_name: str | None
    user_name: str | None
    user_display_name: str | None
    user_email: str | None
    thread_name: str | None
    message_name: str | None
    text: str
    raw: dict[str, Any]
