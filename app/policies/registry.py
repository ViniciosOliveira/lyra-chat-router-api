from dataclasses import dataclass

OWNER_USER = "users/108616006099141003473"
JOAO_VICTOR_USER = "users/100811886516332607168"
RAFAEL_CAMARGO_USER = "users/101466515008395418981"
RAQUEL_DUARTE_USER = "users/102763968224911184184"

MKT_PERFORMANCE_SPACE = "spaces/AAQAiP4nKa4"
MKT_PERFORMANCE_POLICY_KEY = "mkt_performance_analysis_only"
CONTENT_CREATIVES_SPACE = "spaces/AAQATyNL6WE"
CONTENT_CREATIVES_POLICY_KEY = "content_creatives_edune"


@dataclass(frozen=True)
class SpacePolicy:
    key: str
    label: str
    allowed_users: frozenset[str]
    scope: str


TURNSTILE_ALLOWED_USERS = frozenset(
    {
        OWNER_USER,
        "users/108384585713055881619",
        "users/100811886516332607168",
        "users/102876287088758029967",
        "users/102763968224911184184",
        "users/100956834001742974565",
    }
)

CERTIFICATE_ALLOWED_USERS = frozenset(
    {
        OWNER_USER,
        "users/108384585713055881619",
        "users/102836791593473492239",
    }
)

SPACE_POLICIES: dict[str, SpacePolicy] = {
    # Direct/main DM and simple owner-only workspaces currently configured in OpenClaw.
    "spaces/mqWtpSAAAAE": SpacePolicy(
        key="owner_dm",
        label="DM Vinícios",
        allowed_users=frozenset({OWNER_USER}),
        scope="general_owner_only",
    ),
    "spaces/AAQAqr2EWPE": SpacePolicy(
        key="test_lyra",
        label="Teste Lyra",
        allowed_users=frozenset({OWNER_USER}),
        scope="general_owner_only",
    ),
    "spaces/AAQA_-CeRZ4": SpacePolicy(
        key="owner_workspace",
        label="Owner workspace",
        allowed_users=frozenset({OWNER_USER}),
        scope="general_owner_only",
    ),
    # Operational groups mirrored from OpenClaw allowlist.
    "spaces/AAQAPj4LoCM": SpacePolicy(
        key="turnstile_control",
        label="Controle de catraca",
        allowed_users=TURNSTILE_ALLOWED_USERS,
        scope="turnstile_only",
    ),
    "spaces/AAQA3N7lE8k": SpacePolicy(
        key="turnstile_control",
        label="Controle de catraca",
        allowed_users=TURNSTILE_ALLOWED_USERS,
        scope="turnstile_only",
    ),
    "spaces/AAQAKE4s-Ko": SpacePolicy(
        key="dev_group",
        label="Dev / Mission Control",
        allowed_users=frozenset({OWNER_USER}),
        scope="dev_owner_only",
    ),
    "spaces/AAQAqhVlskk": SpacePolicy(
        key="certificates_correios",
        label="Certificados e Correios",
        allowed_users=CERTIFICATE_ALLOWED_USERS,
        scope="certificates_correios_only",
    ),
    # Business policies managed directly by the router.
    MKT_PERFORMANCE_SPACE: SpacePolicy(
        key=MKT_PERFORMANCE_POLICY_KEY,
        label="Comitê de Mkt Performance",
        allowed_users=frozenset({OWNER_USER, JOAO_VICTOR_USER, RAFAEL_CAMARGO_USER}),
        scope="marketing_performance_analysis_only",
    ),
    CONTENT_CREATIVES_SPACE: SpacePolicy(
        key=CONTENT_CREATIVES_POLICY_KEY,
        label="Criativos & Conteúdo — Edune",
        allowed_users=frozenset({OWNER_USER, RAQUEL_DUARTE_USER}),
        scope="content_creatives_edune",
    ),
}


def get_space_policy(space_name: str | None) -> SpacePolicy | None:
    if not space_name:
        return None
    return SPACE_POLICIES.get(space_name)
