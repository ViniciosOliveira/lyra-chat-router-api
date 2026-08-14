import json
from pathlib import Path

from app.googlechat.normalizer import normalize_event
from app.policies.engine import PolicyEngine
from app.policies.intents import Intent

OWNER = "users/108616006099141003473"
JOAO_VICTOR = "users/100811886516332607168"
RAFAEL_CAMARGO = "users/101466515008395418981"
RAQUEL_DUARTE = "users/102763968224911184184"
BIANCA_ROCHA = "users/108384585713055881619"
LUCAS_ZAVODINI = "users/102398808226223128531"


def event_with_text(text: str, space: str = "spaces/AAQAiP4nKa4", user: str = OWNER):
    payload = json.loads(Path("tests/fixtures/googlechat_message.json").read_text())
    payload["space"]["name"] = space
    payload["message"]["name"] = f"{space}/messages/test"
    payload["message"]["thread"]["name"] = f"{space}/threads/test"
    payload["user"]["name"] = user
    payload["message"]["text"] = text
    return normalize_event(payload)


def test_allows_marketing_analysis():
    decision = PolicyEngine().decide(event_with_text("Analisa o CPL do Google Ads"))

    assert decision.decision == "allow"
    assert decision.handler == "analytics_handler"
    assert decision.scope == "marketing_performance_analysis_only"


def test_allows_joao_victor_marketing_analysis():
    decision = PolicyEngine().decide(event_with_text("Analisa o CPL do Google Ads", user=JOAO_VICTOR))

    assert decision.decision == "allow"
    assert decision.handler == "analytics_handler"
    assert decision.scope == "marketing_performance_analysis_only"


def test_allows_rafael_camargo_marketing_analysis():
    decision = PolicyEngine().decide(event_with_text("Analisa o CPL do Google Ads", user=RAFAEL_CAMARGO))

    assert decision.decision == "allow"
    assert decision.handler == "analytics_handler"
    assert decision.scope == "marketing_performance_analysis_only"


def test_allows_lucas_zavodini_marketing_analysis():
    decision = PolicyEngine().decide(
        event_with_text("Gere um relatório de conversão por canal", user=LUCAS_ZAVODINI)
    )

    assert decision.decision == "allow"
    assert decision.handler == "analytics_handler"
    assert decision.scope == "marketing_performance_analysis_only"


def test_allows_joao_victor_roas_campaign_question_with_certificado_context():
    text = (
        "Na conta de anuncio 343-194-0866 eu gostaria de saber a evolução do ROAS "
        "ao longo do tempo das campanhas depois que compra certificado, dentro da curva de atribuição."
    )
    decision = PolicyEngine().decide(event_with_text(text, user=JOAO_VICTOR))

    assert decision.decision == "allow"
    assert decision.handler == "analytics_handler"
    assert decision.scope == "marketing_performance_analysis_only"


def test_allows_joao_victor_course_certificate_spreadsheet_report():
    text = (
        "preciso que me envie uma lista dos ultimos 50 cursos publicados na Unova. "
        "Nome do Curso, URL, quantas matriculas, quantos certificados ja foram comprados, "
        "taxa de matriculados para certificados. Me envie em Google Sheets"
    )
    decision = PolicyEngine().decide(event_with_text(text, user=JOAO_VICTOR))

    assert decision.decision == "allow"
    assert decision.handler == "analytics_handler"
    assert decision.scope == "marketing_performance_analysis_only"



def test_blocks_budget_change():
    decision = PolicyEngine().decide(event_with_text("Aumenta orçamento da campanha X"))

    assert decision.decision == "deny"
    assert decision.handler == "deny_handler"


def test_blocks_deploy():
    decision = PolicyEngine().decide(event_with_text("Faz deploy da tag no site"))

    assert decision.decision == "deny"


def test_allows_owner_dm_space():
    decision = PolicyEngine().decide(event_with_text("me ajuda", space="spaces/mqWtpSAAAAE"))

    assert decision.decision == "allow"
    assert decision.policy_key == "owner_dm"
    assert decision.scope == "general_owner_only"


def test_allows_owner_in_crm_dev_space_with_crm_scope():
    decision = PolicyEngine().decide(
        event_with_text("pode seguir", space="spaces/AAQAKE4s-Ko")
    )

    assert decision.decision == "allow"
    assert decision.policy_key == "crm_dev_group"
    assert decision.scope == "crm_dev_owner_only"


def test_allows_owner_in_mission_control_dev_space_with_mc_scope():
    decision = PolicyEngine().decide(
        event_with_text("pode seguir", space="spaces/AAQAiUi_5No")
    )

    assert decision.decision == "allow"
    assert decision.policy_key == "mission_control_dev_group"
    assert decision.scope == "mission_control_dev_owner_only"


def test_allows_owner_in_edune_v2_dev_space_with_edune_scope():
    decision = PolicyEngine().decide(
        event_with_text("pode seguir", space="spaces/AAQA6YZzBJI")
    )

    assert decision.decision == "allow"
    assert decision.policy_key == "edune_v2_dev_group"
    assert decision.scope == "edune_v2_dev_owner_only"


def test_allows_owner_in_fesn_dev_space_with_fesn_scope():
    decision = PolicyEngine().decide(
        event_with_text("pode seguir", space="spaces/AAQApxfoZm8")
    )

    assert decision.decision == "allow"
    assert decision.policy_key == "fesn_dev_group"
    assert decision.scope == "fesn_dev_owner_only"


def test_allows_owner_in_shared_dev_space_with_shared_scope():
    decision = PolicyEngine().decide(
        event_with_text("pode seguir", space="spaces/AAQA8PyOLEI")
    )

    assert decision.decision == "allow"
    assert decision.policy_key == "shared_dev_group"
    assert decision.scope == "shared_dev_owner_only"


def test_blocks_unknown_space():
    decision = PolicyEngine().decide(event_with_text("me ajuda", space="spaces/UNKNOWN"))

    assert decision.decision == "deny"
    assert decision.policy_key == "unknown_space"


def test_blocks_unauthorized_user_in_known_space():
    decision = PolicyEngine().decide(
        event_with_text("me ajuda", space="spaces/mqWtpSAAAAE", user="users/unauthorized")
    )

    assert decision.decision == "deny"
    assert decision.reason == "User is not allowed for this Google Chat space"


def test_allows_turnstile_scope_in_turnstile_group():
    decision = PolicyEngine().decide(event_with_text("libera entrada da catraca", space="spaces/AAQAPj4LoCM"))

    assert decision.decision == "allow"
    assert decision.handler == "scoped_operation_handler"
    assert decision.scope == "turnstile_only"


def test_blocks_non_turnstile_scope_in_turnstile_group():
    decision = PolicyEngine().decide(event_with_text("faz relatório de marketing", space="spaces/AAQAPj4LoCM"))

    assert decision.decision == "deny"
    assert decision.scope == "turnstile_only"


def test_allows_certificate_scope():
    decision = PolicyEngine().decide(event_with_text("assinar certificado NR", space="spaces/AAQAqhVlskk"))

    assert decision.decision == "allow"
    assert decision.handler == "scoped_operation_handler"
    assert decision.scope == "education_operations_analytics"


def test_allows_correios_scope():
    decision = PolicyEngine().decide(event_with_text("gerar etiqueta correios", space="spaces/AAQAqhVlskk"))

    assert decision.decision == "allow"
    assert decision.handler == "scoped_operation_handler"
    assert decision.scope == "education_operations_analytics"


def test_allows_affirmative_continuation_of_correios_request():
    decision = PolicyEngine().decide(
        event_with_text(
            "@Lyra Sim",
            space="spaces/AAQAqhVlskk",
            user="users/102836791593473492239",
        ),
        continuation_intent=Intent.CORREIOS_LABEL,
    )

    assert decision.decision == "allow"
    assert decision.handler == "scoped_operation_handler"
    assert decision.intent == Intent.CORREIOS_LABEL
    assert decision.continuation is True


def test_continuation_does_not_bypass_user_allowlist():
    decision = PolicyEngine().decide(
        event_with_text(
            "@Lyra Sim",
            space="spaces/AAQAqhVlskk",
            user="users/unauthorized",
        ),
        continuation_intent=Intent.CORREIOS_LABEL,
    )

    assert decision.decision == "deny"
    assert decision.reason == "User is not allowed for this Google Chat space"


def test_allows_bianca_course_sales_report_in_education_operations():
    decision = PolicyEngine().decide(
        event_with_text(
            "Gere um gráfico das vendas de cursos do IS por mês",
            space="spaces/AAQAqhVlskk",
            user=BIANCA_ROCHA,
        )
    )

    assert decision.decision == "allow"
    assert decision.handler == "analytics_handler"
    assert decision.scope == "education_operations_analytics"


def test_allows_bianca_certificate_sales_report_in_education_operations():
    decision = PolicyEngine().decide(
        event_with_text(
            "Preciso de relatório de vendas de certificados na plataforma",
            space="spaces/AAQAqhVlskk",
            user=BIANCA_ROCHA,
        )
    )

    assert decision.decision == "allow"
    assert decision.handler == "analytics_handler"


def test_blocks_campaign_change_in_education_operations():
    decision = PolicyEngine().decide(
        event_with_text(
            "Aumenta o orçamento da campanha",
            space="spaces/AAQAqhVlskk",
            user=BIANCA_ROCHA,
        )
    )

    assert decision.decision == "deny"
    assert decision.scope == "education_operations_analytics"


def test_allows_content_creatives_group():
    decision = PolicyEngine().decide(
        event_with_text("Cria 5 hooks para pós-graduação", space="spaces/AAQATyNL6WE")
    )

    assert decision.decision == "allow"
    assert decision.policy_key == "content_creatives_edune"
    assert decision.scope == "content_creatives_edune"


def test_allows_raquel_in_content_creatives_group():
    decision = PolicyEngine().decide(
        event_with_text(
            "Gera relatório completo dos criativos orgânicos e pagos",
            space="spaces/AAQATyNL6WE",
            user=RAQUEL_DUARTE,
        )
    )

    assert decision.decision == "allow"
    assert decision.scope == "content_creatives_edune"


def test_blocks_operational_execution_in_content_creatives_group():
    decision = PolicyEngine().decide(
        event_with_text("Aumenta orçamento da campanha X", space="spaces/AAQATyNL6WE")
    )

    assert decision.decision == "deny"
    assert decision.handler == "deny_handler"
    assert decision.scope == "content_creatives_edune"
