import json

from groq import Groq

from app.core.config import settings


class GroqAnalysisError(Exception):
    pass


_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def call_groq(prompt: str, client: Groq | None = None) -> dict:
    active_client = client or _get_client()

    try:
        completion = active_client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except Exception as exc:
        raise GroqAnalysisError(f"Groq API request failed: {exc}") from exc

    try:
        content = completion.choices[0].message.content
    except (IndexError, AttributeError) as exc:
        raise GroqAnalysisError(f"Groq returned an unexpected response shape: {exc}") from exc

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise GroqAnalysisError(f"Groq returned invalid JSON: {exc}") from exc
