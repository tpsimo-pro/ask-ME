# Frontend Redesign — Design

## Contexto

O frontend atual (`frontend/src`) é funcional mas totalmente sem estilo: HTML puro,
sem CSS, sem biblioteca de UI. Login, análise de código, histórico e navegação já
funcionam (React + Vite + react-router-dom), mas a experiência visual precisa de
trabalho.

## Objetivo

Redesenhar visualmente as telas existentes, sem alterar rotas, lógica de negócio,
chamadas de API ou fluxo de autenticação. Escopo é puramente visual/UX.

## Direção visual

Tema claro (branco), estética de ferramenta para desenvolvedor:

- Fundo branco, texto escuro, uma cor de destaque (accent) para botões/links/estados.
- Fonte monoespaçada para áreas de código (textarea de input, blocos de resultado).
- Cards com borda sutil/sombra leve para agrupar resultados (sugestões, testes,
  riscos de segurança).
- Espaçamento generoso, hierarquia visual clara entre título, conteúdo e ações.
- Estados visuais explícitos: loading, erro, vazio (sem análise ainda / sem
  histórico ainda).

## Abordagem técnica

- **Tailwind CSS**, instalado como dev dependency e configurado no Vite. Única
  dependência nova.
- Nenhuma mudança em `App.tsx` (rotas), `AuthContext.tsx`, `api/client.ts`, ou nos
  hooks/estado dos componentes — apenas o JSX/markup e classes de estilo.
- Componentes/páginas tocados: `NavBar`, `LoginPage`, `AnalyzePage` (com
  `CodeInput`, `LanguageSelect`), `AnalysisResult`, `HistoryPage`
  (com `HistoryList`), `AuthGuard` (sem alteração — não renderiza UI própria).

## Fora de escopo

- Qualquer mudança de comportamento, rota, chamada de API ou lógica de auth.
- Testes automatizados de UI (não há testes de frontend hoje; não serão
  adicionados nesta tarefa).
- Dark mode / toggle de tema — apenas o tema claro definido acima.

## Critério de pronto

- `npm run build` (tsc + vite build) passa sem erros no `frontend/`.
- App revisado visualmente no browser: login, análise (com resultado), histórico,
  estados de erro/loading, navegação entre as 3 telas.
