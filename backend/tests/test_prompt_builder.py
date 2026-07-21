from app.analysis.prompt_builder import build_prompt


def test_build_prompt_includes_code_language_and_json_keys():
    prompt = build_prompt("print('hi')", "python")

    assert "python" in prompt
    assert "print('hi')" in prompt
    assert "sugestoes" in prompt
    assert "testes_gerados" in prompt
    assert "riscos_seguranca" in prompt
