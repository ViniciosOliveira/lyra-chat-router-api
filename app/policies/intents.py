from enum import StrEnum


class Intent(StrEnum):
    MARKETING_ANALYSIS = "marketing_analysis"
    PERFORMANCE_REPORT = "performance_report"
    ACADEMIC_CATALOG_ANALYSIS = "academic_catalog_analysis"
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
    ACADEMIC_CATALOG_CHANGE = "academic_catalog_change"
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
    Intent.ACADEMIC_CATALOG_CHANGE: [
        "altera o catálogo",
        "alterar o catálogo",
        "muda o catálogo",
        "mudar o catálogo",
        "atualiza o catálogo",
        "atualizar o catálogo",
        "adiciona curso",
        "adicionar curso",
        "remove curso",
        "remover curso",
        "publica curso",
        "publicar curso",
        "edita a grade curricular",
        "editar a grade curricular",
        "altera a grade curricular",
        "alterar a grade curricular",
    ],
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
    Intent.ACADEMIC_CATALOG_ANALYSIS: [
        "comparativo de catálogo",
        "comparativo de catalogo",
        "comparação de catálogo",
        "comparacao de catalogo",
        "comparar catálogos",
        "comparar catalogos",
        "comparar cursos",
        "comparativo entre os cursos",
        "comparativo de cursos",
        "comparativo dos cursos",
        "comparação de cursos",
        "comparacao de cursos",
        "grade curricular",
        "matriz curricular",
        "cursos em comum",
        "cursos que faltam",
        "diferença entre os cursos",
        "diferenca entre os cursos",
    ],
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
        "gráfico",
        "grafico",
        "gráficos",
        "graficos",
        "venda de cursos",
        "vendas de cursos",
        "venda de certificados",
        "vendas de certificados",
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


OWNER_READONLY_ANALYSIS_AUTHORIZATIONS = (
    "pode liberar esse tipo de análise",
    "pode liberar esse tipo de analise",
    "autorizo esse tipo de análise",
    "autorizo esse tipo de analise",
    "pode fazer essa análise",
    "pode fazer essa analise",
)

READONLY_ANALYSIS_CONTINUATION_CUES = (
    "aguardo",
    "concluir",
    "conclua",
    "finalizar",
    "finalize",
    "resultado",
    "cadê",
    "cade",
)

ACADEMIC_ANALYSIS_REFERENCES = (
    "comparativo",
    "comparação",
    "comparacao",
    "cruzamento",
)


def is_owner_readonly_analysis_authorization(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in OWNER_READONLY_ANALYSIS_AUTHORIZATIONS)


def is_readonly_academic_analysis_continuation(text: str) -> bool:
    lowered = text.lower()
    return any(cue in lowered for cue in READONLY_ANALYSIS_CONTINUATION_CUES) and any(
        reference in lowered for reference in ACADEMIC_ANALYSIS_REFERENCES
    )


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
