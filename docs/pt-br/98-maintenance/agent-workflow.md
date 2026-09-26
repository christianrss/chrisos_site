---
id: agent-workflow
lang: pt-br
type: technical-chapter
volume: 98-maintenance
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on: []
related:
  - validation-evidence
---

# Manutenção documental de baixo contexto

## Objetivo

A documentação pode crescer para centenas ou milhares de páginas enquanto um agente normalmente lê uma página e poucos arquivos.

## Grafo de dependências

`sources` registra arquivos concretos, `symbols` identificadores importantes e `depends_on`/`related` relações conceituais.

Mudança de fonte pode ser mapeada a docs sem varrer toda a obra.

## Detecção de obsolescência

`stale_docs.py` compara `reviewed_revision` ao HEAD apenas nas sources declaradas. Mudança não relacionada não força revisão; mudança relevante entra na fila gerada.

## Context packs

`context_pack.py` copia página, fontes, diff, metadata e instruções. Esse é o input normal para agente.

## Fatos gerados

`inventory.py` produz paths, hashes, line counts, includes e symbols detectados. IA não deve gastar tokens reescrevendo esses dados.

## Interpretação autoral

Invariantes, ownership, concorrência, rationale, failure modes e significado de validação continuam em páginas autorais.

## Controle de custo

1. reutilizar análise de fonte inalterada;
2. trabalhar a partir de diff;
3. não regenerar prose não afetada;
4. gerar índices/fatos sem modelo.

Assim o site pode crescer muito mais que o contexto necessário para qualquer atualização comum.
