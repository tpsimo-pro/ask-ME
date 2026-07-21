def build_prompt(code: str, language: str) -> str:
    return (
        "Voce e um analisador de codigo senior. Analise o codigo abaixo, escrito em "
        f"{language}, e responda EXCLUSIVAMENTE com um JSON valido, sem nenhum texto "
        "fora do JSON, no seguinte formato exato:\n"
        '{"sugestoes": ["..."], "testes_gerados": "...", "riscos_seguranca": ["..."]}\n\n'
        "- sugestoes: lista de strings com melhorias de qualidade, legibilidade ou performance.\n"
        "- testes_gerados: uma string contendo codigo de testes unitarios para o codigo, "
        "na mesma linguagem.\n"
        "- riscos_seguranca: lista de strings descrevendo vulnerabilidades ou riscos de "
        "seguranca encontrados (lista vazia se nao houver nenhum).\n\n"
        f"Codigo ({language}):\n```{language}\n{code}\n```"
    )
