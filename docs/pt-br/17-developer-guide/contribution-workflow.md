---
id: contribution-workflow
lang: pt-br
type: guide
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - CONTRIBUTING.md
  - docs/development/workflow.md
  - docs/development/testing.md
  - docs/README.md
depends_on:
  - testing-validation
---

# Fluxo de contribuição

Uma contribuição para o ChrisOS deve ser revisável como uma afirmação de engenharia pequena: problema definido, alteração de código delimitada, evidência apropriada à afirmação e documentação atualizada na camada correta.

## Comece da main atual

~~~bash
git checkout main
git pull --ff-only
git checkout -b <topic-branch>
~~~

Use uma branch temática para uma alteração coerente. Evite misturar artefatos gerados, limpeza não relacionada, reformatação ampla e mudança arquitetural no mesmo pull request.

Antes de editar, identifique o subsistema proprietário do comportamento.

| Área | Local principal |
|---|---|
| CPU, memória, interrupts, SMP, processos | kernel/metal/ |
| storage, filesystem, instalador | kernel/fs/ |
| gráficos, input, 3D, GPU | kernel/gfx/ |
| desktop e janelas | kernel/wm/ |
| rede | kernel/net/ |
| ChrisC, CLVM, JIT e toolchain | compiler/ e kernel/lang/ |
| aplicações guest | APPS/, GAMES/, LIB/, SYS/ |
| ChrisVM | chrisvm/ |

Preserve a fronteira salvo quando a mudança realmente exigir alteração arquitetural de interface.

## Compile continuamente

Escolha o build mais estreito:

~~~bash
make kernel
~~~

para trabalho focado no kernel,

~~~bash
make
~~~

para integração normal e

~~~bash
make chrisvm
make chrisvm-test
~~~

para trabalho em ChrisVM.

Um ciclo focado produz feedback mais rápido e interpretável que executar todas as suítes a cada edição.

## Teste estreito, depois amplo

Exemplos:

~~~bash
make host-cfs-test
make host-kcc-test
make test-qemu-gpu
make test-qemu-xhci
make chrisvm-test
~~~

Depois de estabilizar o caminho específico:

~~~bash
make host-gates
make qemu-gates
~~~

Se um teste relevante não puder ser executado, declare isso no PR em vez de insinuar cobertura.

## Expectativas de código

Contribuições devem preservar restrições próprias de software de sistemas:

- código do kernel deve permanecer freestanding onde o subsistema atual é freestanding;
- não introduza pressupostos de libc do host em código privilegiado do guest;
- preserve ownership e lifetime explícitos;
- preserve ordem de locks e invariantes de sincronização;
- mantenha detalhes de backend/dispositivo atrás das abstrações existentes quando possível;
- trate mudanças de ABI, formato de arquivo e wire format como mudanças de compatibilidade;
- prefira um teste focado a uma afirmação de capacidade sem evidência;
- não desative warnings-as-errors globalmente para esconder um problema local.

Uma correção que faz uma configuração funcionar violando uma abstração costuma criar defeito mais caro em outra camada.

## Artefatos gerados

Não faça commit de build/, ISOs, imagens de disco, objetos ou logs transitórios.

Antes do PR:

~~~bash
git status
git diff --stat
git diff
~~~

Verifique se o patch contém apenas source e documentação intencionais.

## Propriedade da documentação

O repositório ChrisOS mantém apenas documentação operacional que precisa acompanhar comandos exatos da árvore. Arquitetura, comportamento, especificações, status, pesquisa e material educacional pertencem ao chrisos_site.

Atualize o repositório de source quando mudar:

- comandos de setup;
- comandos de build/run;
- nomes de targets de teste;
- mecânica de contribuição.

Atualize o chrisos_site quando mudar:

- arquitetura;
- comportamento de subsistema;
- interfaces ou formatos;
- interpretação de validação;
- capacidade atual;
- roadmap ou contexto de pesquisa.

Uma mesma mudança pode exigir ambos.

## Descrição do pull request

Um PR útil deve registrar:

~~~text
Problema:
Escopo:
Fronteira arquitetural:
Implementação:
Impacto de compatibilidade / ABI / formato:
Testes executados:
Resultados:
Não testado:
Documentação alterada:
~~~

Em correção de bug, inclua a falha observável e, quando possível, teste de regressão.

Em nova capacidade, não trate presença de código como prova de conclusão. Ligue a afirmação à evidência realmente executada.

## Qualidade dos commits

Mantenha commits compreensíveis e focados. O histórico deve permitir entender por que a mudança existe e qual comportamento modifica.

Evite commits que misturem reformatação automática de arquivos não relacionados, binários gerados, movimentação de código com mudança comportamental quando a separação for prática, ou arquivos gerados manualmente editados.

## Revisabilidade

Um revisor deve conseguir responder:

1. Qual comportamento muda?
2. Qual subsistema é proprietário?
3. Qual invariante ou interface mudou?
4. Quais comandos provam o resultado?
5. Qual ambiente relevante não foi testado?

Se isso não estiver claro, o patch é amplo demais ou o registro do PR está incompleto.

## Estratégia para primeira contribuição

A primeira contribuição deve normalmente escolher um defeito delimitado, teste, divergência documental ou melhoria isolada, em vez de começar por redesign transversal.

Formatos úteis:

- adicionar teste de regressão para bug reproduzível;
- corrigir falha determinística em teste host;
- melhorar error path acompanhado de gate;
- corrigir comando operacional divergente da árvore;
- melhorar subsistema sem alterar formato público;
- reconciliar documentação canônica com comportamento verificado.

O objetivo não é evitar trabalho difícil. É estabelecer um ciclo de revisão confiável antes de modificar várias camadas ao mesmo tempo.

## Segurança

Use a política de segurança do repositório para vulnerabilidades ou relatórios que não devem ser publicados em PR público normal. Não exponha detalhes sensíveis apenas para seguir o fluxo comum de contribuição.

## Evidência deve acompanhar o escopo do patch

O registro de validação deve ser proporcional à boundary alterada.

Correção apenas editorial não exige fingir que hardware físico foi requalificado. Mudança em storage driver não deve parar em unit test de compiler sem relação. Mudança de format precisa de evidence de compatibility/rejection, não apenas build bem-sucedido.

O objetivo não é maximizar quantidade de comandos no pull request. É escolher tests cujos oracles exercitem diretamente invariant, interface ou failure path alterado e depois usar gates mais amplos como confirmação de regressão.

## Review de compatibilidade

Antes de mergear mudança em ABI, serialized format, syscall, object format ou boot contract, responda explicitamente se producers e consumers existentes continuam compatíveis.

Se a compatibilidade mudar, o PR deve identificar version afetada, migration ou rejection behavior e os tests que exercitam artifacts antigos e novos. Tratar compatibility change como refactor comum torna debugging futuro muito mais difícil.

## Mantenha mudanças de compatibilidade explícitas

Se o patch altera on-disk format, bytecode image, ABI, boot contract ou semantics públicas de resource, registre isso separadamente do resumo de implementação.

O reviewer deve conseguir identificar:

- se artifacts antigos continuam legíveis;
- se writers novos emitem nova version;
- se migration é necessária;
- se unknown versions ou flags falham de forma fechada;
- quais regression fixtures cobrem a compatibilidade.

Não esconda mudança de compatibilidade dentro de refactor amplo. Decidir version explicitamente custa menos que diagnosticar cross-revision breakage silencioso depois.

## Antes de abrir o PR

Execute:

~~~bash
git status
./scripts/check-dev-env.sh
make <narrow-target>
make <relevant-test>
~~~

Depois rode o gate mais amplo viável para a área. Registre resultados e skips exatos.

Qualidade de contribuição no ChrisOS é definida por rastreabilidade: source, evidência e documentação devem contar a mesma história.
