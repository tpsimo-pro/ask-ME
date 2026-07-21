from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_LANGUAGES = {
    "javascript",
    "typescript",
    "python",
    "java",
    "go",
    "csharp",
    "cpp",
    "ruby",
    "php",
}


class AnalyzeRequest(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=20000)
    linguagem: str

    @field_validator("linguagem")
    @classmethod
    def validate_language(cls, value: str) -> str:
        if value not in ALLOWED_LANGUAGES:
            raise ValueError(f"linguagem deve ser uma de: {sorted(ALLOWED_LANGUAGES)}")
        return value


class AnalyzeResponse(BaseModel):
    sugestoes: List[str]
    testes_gerados: str
    riscos_seguranca: List[str]


class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    language: str
    code_snippet: str
    created_at: datetime
