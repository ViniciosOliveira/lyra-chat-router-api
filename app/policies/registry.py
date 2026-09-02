from dataclasses import dataclass

OWNER_USER = "users/108616006099141003473"
BIANCA_ROCHA_USER = "users/108384585713055881619"
LUCAS_ZAVODINI_USER = "users/102398808226223128531"
JOAO_VICTOR_USER = "users/100811886516332607168"
RAFAEL_CAMARGO_USER = "users/101466515008395418981"
RAQUEL_DUARTE_USER = "users/102763968224911184184"

MKT_PERFORMANCE_SPACE = "spaces/AAQAiP4nKa4"
MKT_PERFORMANCE_POLICY_KEY = "mkt_performance_analysis_only"
EDUNE_CMO_DM_SPACE = "spaces/kf-dfKAAAAE"
CONTENT_CREATIVES_SPACE = "spaces/AAQATyNL6WE"
CONTENT_CREATIVES_POLICY_KEY = "content_creatives_edune"
CRM_DEV_SPACE = "spaces/AAQAKE4s-Ko"
MISSION_CONTROL_DEV_SPACE = "spaces/AAQAiUi_5No"
EDUNE_V2_DEV_SPACE = "spaces/AAQA6YZzBJI"
FESN_DEV_SPACE = "spaces/AAQApxfoZm8"
SHARED_DEV_SPACE = "spaces/AAQA8PyOLEI"
LYRA_OS_PRODUCT_OPERATIONS_SPACE = "spaces/AAQAhfNho-0"


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
        BIANCA_ROCHA_USER,
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
    EDUNE_CMO_DM_SPACE: SpacePolicy(
        key=MKT_PERFORMANCE_POLICY_KEY,
        label="DM Lucas — Edune CMO",
        allowed_users=frozenset({LUCAS_ZAVODINI_USER}),
        scope="edune_cmo_readonly",
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
    CRM_DEV_SPACE: SpacePolicy(
        key="crm_dev_group",
        label="Dev - CRM",
        allowed_users=frozenset({OWNER_USER}),
        scope="crm_dev_owner_only",
    ),
    MISSION_CONTROL_DEV_SPACE: SpacePolicy(
        key="mission_control_dev_group",
        label="Dev - Mission Control",
        allowed_users=frozenset({OWNER_USER}),
        scope="mission_control_dev_owner_only",
    ),
    EDUNE_V2_DEV_SPACE: SpacePolicy(
        key="edune_v2_dev_group",
        label="Dev - Edune 2.0",
        allowed_users=frozenset({OWNER_USER}),
        scope="edune_v2_dev_owner_only",
    ),
    FESN_DEV_SPACE: SpacePolicy(
        key="fesn_dev_group",
        label="Dev - Fesn",
        allowed_users=frozenset({OWNER_USER}),
        scope="fesn_dev_owner_only",
    ),
    SHARED_DEV_SPACE: SpacePolicy(
        key="shared_dev_group",
        label="Dev - Shared",
        allowed_users=frozenset({OWNER_USER}),
        scope="shared_dev_owner_only",
    ),
    LYRA_OS_PRODUCT_OPERATIONS_SPACE: SpacePolicy(
        key="lyra_os_product_operations",
        label="LyraOS — Produto & Operação",
        allowed_users=frozenset({OWNER_USER}),
        scope="lyra_os_product_operations_owner_only",
    ),
    "spaces/AAQAqhVlskk": SpacePolicy(
        key="education_operations",
        label="Comitê - Operações Educacionais",
        allowed_users=CERTIFICATE_ALLOWED_USERS,
        scope="education_operations_analytics",
    ),
    # Business policies managed directly by the router.
    MKT_PERFORMANCE_SPACE: SpacePolicy(
        key=MKT_PERFORMANCE_POLICY_KEY,
        label="Comitê de Mkt Performance",
        allowed_users=frozenset(
            {OWNER_USER, JOAO_VICTOR_USER, RAFAEL_CAMARGO_USER, LUCAS_ZAVODINI_USER}
        ),
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
