from enum import StrEnum


class Intent(StrEnum):
    MARKETING_ANALYSIS = "marketing_analysis"
    PERFORMANCE_REPORT = "performance_report"
    TRACKING_DIAGNOSIS = "tracking_diagnosis"
    METRIC_EXPLANATION = "metric_explanation"
    RECOMMENDATION = "recommendation"
    CAMPAIGN_CHANGE = "campaign_change"
    BUDGET_CHANGE = "budget_change"
    TAG_CHANGE = "tag_change"
    PIXEL_CHANGE = "pixel_change"
    CODE_CHANGE = "code_change"
    DEPLOY = "deploy"
    EXTERNAL_MESSAGE_SEND = "external_message_send"
    TURNSTILE_CONTROL = "turnstile_control"
    CERTIFICATE_SIGNING = "certificate_signing"
    CORREIOS_LABEL = "correios_label"
    UNKNOWN_OPERATIONAL_EXECUTION = "unknown_operational_execution"
    UNKNOWN = "unknown"


BLOCKING_KEYWORDS = {
    Intent.BUDGET_CHANGE: ["aumenta orçamento", "aumentar orçamento", "reduz orçamento", "muda orçamento"],
    Intent.CAMPAIGN_CHANGE: ["pausa campanha", "pausar campanha", "ativa campanha", "editar campanha"],
    Intent.TAG_CHANGE: ["instala tag", "alterar tag", "mudar tag", "taguear"],
    Intent.PIXEL_CHANGE: ["instala pixel", "alterar pixel", "mudar pixel"],
    Intent.CODE_CHANGE: ["altera o código", "mexe no código", "commit", "merge"],
    Intent.DEPLOY: ["deploy", "publica em produção", "subir produção"],
    Intent.EXTERNAL_MESSAGE_SEND: ["manda mensagem", "envia para", "dispara"],
}

OPERATIONAL_SCOPE_KEYWORDS = {
    Intent.TURNSTILE_CONTROL: [
        "catraca",
        "libera entrada",
        "liberar entrada",
        "libera saída",
        "liberar saída",
        "libera saida",
        "liberar saida",
        "modo livre",
        "voltar ao normal",
    ],
    Intent.CERTIFICATE_SIGNING: [
        "certificado",
        "certificados",
        "assinar certificado",
        "assinatura de certificado",
        "nr",
    ],
    Intent.CORREIOS_LABEL: [
        "correios",
        "etiqueta",
        "etiquetas",
        "código de postagem",
        "codigo de postagem",
    ],
}

ANALYSIS_KEYWORDS = {
    Intent.PERFORMANCE_REPORT: [
        "relatório",
        "report",
        "resumo",
        "resultado",
        "lista",
        "planilha",
        "google sheets",
        "sheet",
        "dados",
        "últimos 50 cursos",
        "ultimos 50 cursos",
        "certificados comprados",
        "certificados vendidos",
        "certificados emitidos",
    ],
    Intent.TRACKING_DIAGNOSIS: ["tracking", "utm", "pixel", "evento", "tag", "atribuição", "atribuicao"],
    Intent.METRIC_EXPLANATION: ["cpl", "cac", "roas", "cpa", "ctr", "conversão", "conversao", "taxa", "matrículas", "matriculas"],
    Intent.RECOMMENDATION: ["recomenda", "o que fazer", "próximo passo", "sugere"],
    Intent.MARKETING_ANALYSIS: [
        "analisa",
        "análise",
        "analise",
        "google ads",
        "meta ads",
        "performance",
        "campanha",
        "campanhas",
        "conta de anuncio",
        "conta de anúncio",
        "evolução",
        "evolucao",
        "curva de atribuição",
        "curva de atribuicao",
    ],
}


def classify_intent(text: str) -> Intent:
    lowered = text.lower()
    for intent, keywords in BLOCKING_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return intent
    # Analysis must be evaluated before scoped operational keywords. In marketing
    # contexts, words like "certificado" can describe the course/product or a
    # purchase event, not certificate-signing execution.
    for intent, keywords in ANALYSIS_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return intent
    for intent, keywords in OPERATIONAL_SCOPE_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return intent
    return Intent.UNKNOWN
