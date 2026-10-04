---
id: fuzzing
lang: pt-br
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - makefile
  - tools/test_fuzz_cfs.c
  - tools/test_fuzz_elf.c
  - tools/test_fuzz_chrisc.c
  - tools/test_fuzz_clvm.c
  - tools/test_elf_malformed.c
  - tools/test_shader.c
  - chrisvm/tests/test_chrisvm.c
symbols: []
depends_on:
  - host-tests
  - fault-injection
related:
  - performance-measurement
  - chrisfs
  - clvm
  - shader-pipeline
  - chrisvm
---

# Fuzzing de parsers e formatos

## Escopo

O ChrisOS já usa testes fuzz-like em várias fronteiras de input de alto risco.

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, os principais targets determinísticos cobrem:

- paths/operações ChrisFS;
- input do ELF loader;
- source ChrisC;
- parsing de images CLVM;
- instruction decoding do ChrisVM;
- alguns casos malformados de shader/CSI.

A descrição precisa é **fuzzing pseudo-randômico determinístico em host mais testes estruturados de input malformado**.

Ainda não é uma plataforma de coverage-guided fuzzing.

Não existe integração geral com libFuzzer/AFL, gestão persistente de corpus, minimização automática, mutation feedback loop ou métrica de coverage para os fuzzers.

## Por que essas fronteiras importam

Parser converte bytes/texto não confiáveis em estado interno.

A transição perigosa é:

[
	ext{input não confiável} ightarrow 	ext{representação interna confiável}
]

Bugs podem causar:

- acesso out-of-bounds;
- integer overflow;
- stale state;
- resource leak;
- control flow inválido;
- corrupção de filesystem;
- aceitação de executável malformado.

Para um sistema operacional, parsers e formatos binários são alvos de alto valor mesmo antes de existir ampla exposição de rede.

## Geradores pseudo-randômicos determinísticos

Os fuzz tests dedicados usam geradores lineares congruenciais simples.

Uma recorrência representativa é:

[
s_{n+1} = 1664525s_n + 1013904223 pmod{2^{32}}
]

As seeds são constantes no código.

Exemplos:

    0xC0FFEE
    0xC1A55E
    1

Isso torna CI reproduzível.

A mesma revisão executa a mesma sequência.

A limitação é que runs repetidos não exploram espaço novo se seed, generator e iteration count não mudarem.

## Fuzzing versus random testing

"Fuzzing" cobre níveis diferentes de sofisticação.

Os testes atuais usam principalmente:

1. geração determinística de bytes/texto;
2. casos malformados escritos à mão;
3. post-condition checks;
4. invariants de cleanup.

Eles não usam coverage para evoluir inputs.

A afirmação correta é:

> ChrisOS exercita conjuntos determinísticos de inputs adversariais em cada execução normal de host gates.

Não deve ser descrito como fuzzing exaustivo ou coverage-guided.

## Target ChrisFS

`tools/test_fuzz_cfs.c` cria block device em memória, formata ChrisFS e faz mount.

Depois executa 200 iterações.

Cada uma gera path de comprimento:

    rnd() % 48

com bytes aproximadamente imprimíveis.

Para cada path tenta:

    cfs_mkdir
    cfs_write
    cfs_read
    cfs_unlink

Os return codes não precisam indicar sucesso.

Names inválidos podem e devem ser rejeitados.

O invariant principal é integridade do filesystem depois da sequência adversarial.

Ao final:

    cfs_fsck(&fs)

precisa retornar `CFS_OK`.

## Oracle do ChrisFS

O teste não pergunta:

> Toda operação random funcionou?

Ele pergunta:

> Após operações válidas e inválidas, a estrutura do filesystem continua consistente?

Esse é um oracle mais forte para robustez de path/parser.

Pode ser melhorado com:

- remount;
- conservação de allocation bitmap;
- ausência de blocks/inodes inalcançáveis;
- persistência de um subconjunto de arquivos válidos;
- fsck repetido após crashes simulados.

## Target ELF

`tools/test_fuzz_elf.c` gera 300 inputs.

Cada input tem 1 a 256 bytes.

O buffer recebe dados pseudo-randômicos.

Em aproximadamente uma de cada oito iterações, os quatro primeiros bytes viram:

    0x7f 'E' 'L' 'F'

Isso empurra alguns inputs mais profundamente no parser em vez de todos morrerem imediatamente no magic.

Essa pequena estrutura aumenta exploração útil.

## Oracle ELF sob pressão de recursos

O fuzzer também limita o fake page allocator.

Antes de cada load:

    g_budget = 4

O teste registra quantidade de pages, chama `elf_load` e valida cleanup.

Quando load falha, exige:

- allocated-page count igual ao valor anterior;
- current process restaurado para 0.

Isso detecta cleanup bugs, não apenas crashes.

Se um input leva o loader a alocar estado antes de falhar, tudo precisa ser liberado.

## Suíte ELF estruturada

`tools/test_elf_malformed.c` complementa o fuzz random.

Contém casos nomeados para:

- truncation;
- bad magic;
- offset overflow;
- address overflow;
- `filesz > memsz`;
- segments sobrepostos;
- W+X;
- invalid entry point;
- unsupported program header;
- OOM durante load.

Não é fuzzing randômico.

É um regression corpus de invariants semânticos conhecidos.

Os dois estilos devem coexistir:

    exploração random + casos nomeados

Um fuzzer coverage-guided futuro deve usar esses casos como seeds de corpus.

## Target ChrisC

`tools/test_fuzz_chrisc.c` ataca o frontend ChrisC.

Executa 48 iterações.

Cada source tem menos de 180 bytes e caracteres ASCII imprimíveis.

O compiler usa buffer de output fixo.

O resultado precisa permanecer nos status normais de success/failure; return code inesperado falha o teste.

Depois dos inputs adversariais, compila um programa válido:

    int main(){return 1;}

Esse controle verifica se inputs anteriores não deixaram state do compiler corrompido.

## Limitações do ChrisC fuzz

O fuzzer é propositalmente pequeno.

Ainda não:

- preserva inputs interessantes;
- entende grammar;
- muta programas ChrisC válidos;
- gera ASTs profundos;
- varia include graphs;
- mira type/semantic boundaries;
- usa coverage feedback.

Um mutator grammar-aware alcançaria caminhos mais profundos, porque texto random frequentemente falha no lexer/parser inicial.

## Target CLVM

`tools/test_fuzz_clvm.c` executa 200 iterações em buffers de até 96 bytes.

Cada buffer é enviado para:

    clvm_parse

O enum retornado deve permanecer dentro do range definido de `ClvmLoadError`.

A mensagem associada ao erro também deve ser não nula.

Depois dos inputs random, o teste cria image válida com:

    clvm_write_image

e confirma parse com `CL_LOAD_OK` e code size esperado.

Isso prova:

1. input inválido permanece dentro da semântica de erro;
2. a atividade adversarial não quebra o caminho válido encode/decode.

## Fuzzing do decoder ChrisVM

`chrisvm/tests/test_chrisvm.c` contém `test_fuzz_decode`.

São 2000 iterações determinísticas.

Cada caso gera entre 1 e 15 bytes e chama o decoder.

O resultado deve ser:

    -1

para input inválido, ou tamanho de 1 a 15 com:

    insn.len == return_value

O invariant é bounded decoding.

O decoder não pode afirmar comprimento impossível de instrução x86 nem retornar metadata inconsistente.

## Fronteira de execução ChrisVM

Esse target valida decode, não execução arbitrária.

Uma sequência que decodifica com sucesso não é automaticamente executada pelo modelo completo CPU/MMU/devices.

O trabalho futuro deve separar:

- decode fuzzing;
- semantic instruction fuzzing;
- differential execution;
- MMU/page-fault fuzzing;
- device-register fuzzing.

Cada um exige oracle diferente.

## Shader e CSI

`tools/test_shader.c` contém `test_csi_guest_fuzz`.

O teste cria shader/CSI válido, serializa/recarrega e depois muta dados.

Também fornece pequeno conjunto de shader sources deliberadamente ruins e input com identificador grande.

Além disso verifica ownership de handles no guest.

Isso é melhor classificado como **structured adversarial testing**, não broad random fuzzing.

A suite final verifica que live shader resources retornam ao valor inicial.

Esse cleanup invariant é importante para compilation repetida.

## Integração aos gates

Os quatro targets dedicados são:

    host-fuzz-cfs-test
    host-fuzz-elf-test
    host-fuzz-chrisc-test
    host-fuzz-clvm-test

Eles fazem parte de:

    host-gates

e também:

    host-stress

Os casos shader passam por:

    host-shader-test

que também faz parte de `host-gates`.

O decode fuzz do ChrisVM pertence à suite separada:

    make chrisvm-test

e não aparece na dependency list principal de `host-gates`.

## Auditoria do grafo

O grafo host é verificado por:

    tools/check_test_gates.py

Isso reduz risco de um novo target existir mas não ser alcançado pelo aggregate gate.

Porém auditoria de reachability não mede qualidade de fuzzing.

Um target conectado ainda pode ter diversidade baixa ou oracle fraco.

## Relação com sanitizers

O repositório tem:

    host-sanitize

com AddressSanitizer e UndefinedBehaviorSanitizer para alguns host tests.

Na revisão analisada, os fuzz targets dedicados são compilados pelas recipes normais, sem ASan/UBSan.

É uma oportunidade evidente de melhoria.

Sanitizer transforma corruption silenciosa em falha imediata e reproduzível.

## Projeto de oracles

Fuzzer é tão forte quanto seu oracle.

Oracles atuais úteis incluem:

- return code dentro do domínio definido;
- nenhum resource leak após rejeição;
- current process restaurado;
- fsck limpo;
- input de controle válido continua aceito;
- parser error message não nula;
- instruction length limitado;
- live-resource count volta ao baseline.

"Não crashou" sozinho é oracle fraco.

O projeto já tem vários invariants semânticos que podem ser ampliados.

## Gestão de seeds

Seeds fixas deixam CI estável, mas limitam exploração.

Um desenho futuro deve ter dois modos.

### CI

Conjunto fixo de seeds publicadas.

Garante regressão determinística.

### Exploration

Múltiplas seeds por long runs.

Toda falha precisa registrar:

- seed;
- target;
- iteration;
- input length;
- artifact exato;
- revisão.

O primeiro failing input deve ser minimizado e adicionado ao corpus determinístico.

## Gestão de corpus

Atualmente não há corpus persistente dedicado a esses fuzzers.

Uma estrutura futura:

    fuzz/corpus/elf/
    fuzz/corpus/clvm/
    fuzz/corpus/chrisc/
    fuzz/corpus/cfs/
    fuzz/corpus/chrisvm-decode/
    fuzz/corpus/shader/

Cada bug corrigido deve deixar um reproducer mínimo.

Assim descobertas anteriores viram regression coverage permanente.

## Coverage-guided fuzzing

Coverage-guided fuzzing escolhe mutações futuras conforme novos control-flow edges são atingidos.

Conceitualmente:

[
score(x) propto new_coverage(x)
]

É diferente do random stream fixo atual.

Integrações futuras podem usar compiler instrumentation compatível com libFuzzer ou ferramentas da família AFL.

O production code testado deve permanecer o mesmo sempre que possível; harness e instrumentation ficam no host.

## Fuzzing grammar-aware

Alguns formatos têm estrutura suficiente para tornar byte mutation ineficiente.

Geradores de alto valor incluem:

- ELF program headers;
- CLVM headers/sections/opcodes;
- tokens/AST ChrisC;
- grammar de shader e CSI;
- árvores de paths/operações ChrisFS;
- prefixes/opcodes/addressing modes do ChrisVM.

Generator grammar-aware preserva estrutura externa válida e empurra mutação para boundaries semânticos profundos.

## Fuzzing stateful

ChrisFS é stateful.

Seu input real é uma sequência:

[
S = (op_1, op_2, ldots, op_n)
]

com create, write, rename, unlink, mkdir, read, remount e fsck.

O teste atual já aproxima essa abordagem.

Um fuzzer mais forte deve preservar a sequência que falhou e minimizar a lista de operações.

## Differential testing

Quando existe implementação/modelo alternativo, differential testing fornece oracle forte.

Exemplos futuros:

- decoder ChrisVM versus disassembler de referência no subset suportado;
- interpreter/JIT/native para o mesmo programa;
- shader software versus cálculos de referência;
- modelo lógico ChrisFS versus state on-disk.

Discordância não prova qual implementação está certa, mas produz caso de alta prioridade.

## Orçamento de tempo

Fuzzing pode consumir tempo ilimitado.

A hierarquia deve separar:

- deterministic smoke fuzzing rápido em todo commit;
- sanitizer fuzzing em CI/nightly;
- long exploration campaigns fora do build normal;
- regression cases minimizados e permanentes.

Os testes atuais são pequenos o suficiente para gate comum.

Campanhas longas não devem destruir feedback de desenvolvimento.

## Relevância de segurança

Fuzzing é particularmente importante em boundaries que processam dados malformados ou controlados por usuário.

Áreas prioritárias:

- ELF loader;
- compiler/VM images;
- filesystem names/metadata;
- shader input;
- futuros network parsers.

Crash encontrado por fuzz deve ser classificado por reachability e privilege boundary, não automaticamente chamado de vulnerabilidade.

## Resumo atual

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`:

- ChrisFS: 200 operações/paths random determinísticos + fsck;
- ELF: 300 byte inputs, magic ELF periódico e checks de cleanup sob allocation pressure;
- ChrisC: 48 sources ASCII random + compilação de controle válida;
- CLVM: 200 buffers random + valid round-trip;
- ChrisVM decoder: 2000 byte sequences determinísticas na suite ChrisVM;
- shader/CSI: casos estruturados de mutation/malformed input;
- fuzzers dedicados CFS/ELF/ChrisC/CLVM participam de `host-gates` e `host-stress`.

É cobertura adversarial relevante, mas ainda não coverage-guided.

## Próximos passos

Prioridades:

1. executar fuzzers dedicados sob ASan/UBSan;
2. adicionar modo multi-seed reproduzível;
3. persistir failing inputs automaticamente;
4. minimizar falhas e criar corpus de regressão;
5. adicionar coverage instrumentation;
6. criar mutation grammar-aware para ChrisC/CLVM/ELF;
7. ampliar ChrisFS para stateful operation sequences;
8. fuzzar execução ChrisVM após decode válido;
9. adicionar invariants específicos por parser;
10. publicar fuzz duration, executions e coverage em CI artifacts.

## Nota de revisão

Este capítulo foi reconciliado contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

O repositório já executa testes determinísticos de inputs adversariais durante validação normal. O próximo nível de maturidade é manter essa reprodutibilidade enquanto adiciona sanitizers, corpus, coverage feedback e minimização automática.
