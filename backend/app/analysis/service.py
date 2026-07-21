from app.analysis.groq_client import call_groq, GroqAnalysisError
from app.analysis.prompt_builder import build_prompt
from app.analysis.schemas import AnalyzeResponse

_RETRY_SUFFIX = (
    "\n\nATENCAO: sua resposta anterior nao estava em JSON valido no formato pedido. "
    "Responda novamente APENAS com o JSON exato no formato especificado, sem texto adicional."
)


class AnalysisFailedError(Exception):
    pass


def run_analysis(code: str, language: str) -> AnalyzeResponse:
    prompt = build_prompt(code, language)

    result = _try_analyze(prompt)
    if result is None:
        result = _try_analyze(prompt + _RETRY_SUFFIX)

    if result is None:
        raise AnalysisFailedError("Groq did not return a valid analysis after retry")

    return result


def _try_analyze(prompt: str) -> AnalyzeResponse | None:
    try:
        raw = call_groq(prompt)
        return AnalyzeResponse(**raw)
    except (GroqAnalysisError, TypeError, ValueError):
        return None
