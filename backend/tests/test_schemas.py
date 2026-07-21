import pytest
from pydantic import ValidationError

from app.analysis.schemas import AnalyzeRequest


def test_analyze_request_accepts_allowed_language():
    request = AnalyzeRequest(codigo="print(1)", linguagem="python")
    assert request.linguagem == "python"


def test_analyze_request_rejects_unknown_language():
    with pytest.raises(ValidationError):
        AnalyzeRequest(codigo="print(1)", linguagem="cobol")


def test_analyze_request_rejects_empty_code():
    with pytest.raises(ValidationError):
        AnalyzeRequest(codigo="", linguagem="python")


def test_analyze_request_rejects_code_over_20000_chars():
    with pytest.raises(ValidationError):
        AnalyzeRequest(codigo="x" * 20001, linguagem="python")
