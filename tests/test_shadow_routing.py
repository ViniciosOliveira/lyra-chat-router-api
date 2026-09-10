from app.core.config import Settings
from app.googlechat.schemas import NormalizedChatEvent
from app.handlers import openclaw_agent_hook, openclaw_forward
from app.policies.engine import PolicyDecision
from app.policies.intents import Intent


OWNER_DM = "spaces/mqWtpSAAAAE"
OTHER_SPACE = "spaces/AAQAqr2EWPE"


def event(space: str) -> NormalizedChatEvent:
    return NormalizedChatEvent(
        event_type="MESSAGE",
        space_name=space,
        space_display_name="test",
        user_name="users/108616006099141003473",
        user_display_name="Vinícios Oliveira",
        user_email="vinicios@grupooliveirarocha.com",
        thread_name=None,
        message_name=f"{space}/messages/test",
        text="teste",
        raw={},
    )


def decision() -> PolicyDecision:
    return PolicyDecision(
        policy_key="owner_dm",
        intent=Intent.UNKNOWN,
        decision="allow",
        handler="openclaw_forward",
        reason="Owner allowed",
        scope="general_owner_only",
    )


def settings() -> Settings:
    return Settings(
        openclaw_forward_url="http://10.0.0.5:18789/googlechat",
        openclaw_shadow_space=OWNER_DM,
        openclaw_shadow_forward_url="http://10.0.0.5:18790/googlechat",
        openclaw_agent_hook_url="http://10.0.0.5:18789/hooks/agent",
        openclaw_agent_hook_token="old-token",
        openclaw_shadow_agent_hook_url="http://10.0.0.5:18790/hooks/agent",
        openclaw_shadow_agent_hook_token="new-token",
    )


def test_sync_forward_uses_shadow_only_for_exact_owner_dm():
    cfg = settings()
    assert openclaw_forward._forward_target(cfg, OWNER_DM) == "http://10.0.0.5:18790/googlechat"
    assert openclaw_forward._forward_target(cfg, OTHER_SPACE) == "http://10.0.0.5:18789/googlechat"


def test_agent_hook_uses_shadow_url_and_token_only_for_exact_owner_dm(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs["headers"]["Authorization"]))

        class Response:
            status_code = 200
            text = '{"status":"accepted"}'

            @staticmethod
            def json():
                return {"status": "accepted"}

        return Response()

    monkeypatch.setattr(openclaw_agent_hook.requests, "post", fake_post)
    cfg = settings()
    for space in (OWNER_DM, OTHER_SPACE):
        openclaw_agent_hook._post_agent_hook(
            settings=cfg,
            event=event(space),
            decision=decision(),
        )

    assert calls == [
        ("http://10.0.0.5:18790/hooks/agent", "Bearer new-token"),
        ("http://10.0.0.5:18789/hooks/agent", "Bearer old-token"),
    ]
