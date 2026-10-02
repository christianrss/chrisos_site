---
id: chrisld
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisld/chrisld.h
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chriso.c
  - compiler/chrisasm/chrisasm.c
  - kernel/tools/native_link.c
  - kernel/tools/chrisbuild.c
  - tools/test_chrisld.c
symbols:
  - chrisld_link
  - chrisld_link_objects
  - chrisld_validate
  - resolve_sym
  - duplicate_globals
  - LdMap
  - sym_addr
  - reloc_site
  - apply_one
  - pack_sec
  - wr_phdr
depends_on:
  - native-toolchain
  - chriso
  - chrisasm
  - elf-linking
  - calling-conventions
related:
  - kcc
  - self-hosting-bootstrap
  - linker-script
  - internal-kernel-build
---

# ChrisLd

## Escopo

ChrisLd é o linker nativo do toolchain experimental do ChrisOS. Ele consome uma ou mais imagens de objeto ChrisO, resolve símbolos e relocations, organiza suas seções e produz um executável ELF64 para x86-64.

O caminho atual é:

    objetos ChrisO
        -> verificação de globais duplicados
        -> empacotamento por seção
        -> resolução de símbolos
        -> aplicação de relocations
        -> layout ELF64 ET_EXEC
        -> validação estrutural

ChrisLd não é wrapper de GNU ld, lld, mold ou linker do host. A imagem ELF é escrita diretamente pelo código do projeto em compiler/chrisld/chrisld.c.

Seu objetivo atual é mais estreito que o de um linker ELF de produção. Ele implementa os contratos necessários aos experimentos do toolchain nativo do ChrisOS, mantendo a implementação pequena o suficiente para execução em ambiente freestanding.

## Interface pública

compiler/chrisld/chrisld.h expõe três pontos de entrada:

    int chrisld_link(const ChrisoImage *img, uint64_t load_addr,
                     void *out, uint32_t cap, uint64_t *entry_out);

    int chrisld_link_objects(const ChrisoImage *const *imgs, uint32_t n,
                             uint64_t load_addr, void *out, uint32_t cap,
                             uint64_t *entry_out);

    int chrisld_validate(const void *elf, uint32_t n);

chrisld_link é um wrapper de conveniência para um único objeto.

chrisld_link_objects é o linker multiobjeto efetivo. Ele aceita até 32 objetos porque a estrutura interna de mapeamento possui dimensão fixa de objetos.

chrisld_validate verifica propriedades estruturais importantes do ELF produzido. É um helper de validação, não um verificador ELF completo para entradas hostis.

O header também define CHRISLD_ELF_MAX como um MiB. Essa constante é usada pela integração in-kernel atual como política de buffer de saída. O núcleo do linker continua respeitando a capacidade fornecida pelo chamador.

## Contrato dos objetos de entrada

ChrisLd consome objetos ChrisoImage.

Cada objeto pode fornecer quatro seções lógicas:

- text;
- rodata;
- data;
- BSS.

Também carrega tabela de símbolos e tabela de relocations.

ChrisLd não faz parsing de assembly nem de C. Quando o fluxo chega a essa camada, os bytes de instrução já existem e referências não resolvidas estão representadas como relocations ChrisO.

A separação é fundamental: ChrisAsm decide o encoding das instruções; ChrisLd decide o posicionamento final.

## Limite fixo de objetos

LdMap contém internamente:

    at[4][32]

portanto uma chamada de link aceita no máximo 32 imagens ChrisO.

A função rejeita:

- array de objetos nulo;
- zero objetos;
- mais de 32 objetos;
- ponteiro de saída nulo;
- ponteiro entry_out nulo;
- qualquer elemento nulo dentro do array.

É um limite explícito da implementação de capacidade fixa.

O manifest do builder in-kernel pode listar mais fontes C que o linker aceita diretamente. Essa é uma das razões pelas quais o builder atual usa um caminho intermediário de merge apenas de text, em vez de entregar cada unidade compilada diretamente ao chrisld_link_objects.

## Definições globais duplicadas

Antes do layout das seções, ChrisLd executa duplicate_globals.

O algoritmo examina cada símbolo global definido de cada objeto e o compara com símbolos globais dos objetos posteriores.

Se o mesmo nome global estiver definido em mais de um objeto, o link falha.

Para N objetos e contagens S_i, a estratégia é conceitualmente quadrática na quantidade total de definições globais, pois usa scans aninhados.

Isso é aceitável para conjuntos pequenos e fixos, mas não é uma estratégia escalável de symbol table para linker de grande porte.

Uma tabela global baseada em hash reduziria o custo de lookup e de detecção de duplicidade.

## Regras de resolução de símbolos

resolve_sym implementa o modelo atual.

Se o símbolo referenciado já estiver definido e não for global, ele é resolvido dentro do próprio objeto de origem.

Caso contrário, ChrisLd percorre todos os objetos procurando um símbolo global definido com o mesmo nome.

É exigida uma única definição global.

Se uma segunda definição global coincidente for encontrada, a resolução falha.

Se um símbolo indefinido não encontrar definição global, a resolução falha.

Não há modelo de precedência de weak symbols, symbol versioning, política de visibility, extração de archives ou resolução dinâmica.

O modelo é intencionalmente estrito:

- definições locais permanecem locais;
- definições globais precisam ser únicas;
- referências indefinidas precisam encontrar exatamente uma definição global.

## Empacotamento das seções

Antes de copiar bytes, pack_sec calcula onde começa a contribuição de cada objeto dentro de cada seção combinada.

Para cada seção, as contribuições dos objetos são concatenadas na ordem de entrada.

Depois da primeira contribuição não vazia, a próxima contribuição não vazia é alinhada em 16 bytes.

Para objeto i e seção s, LdMap.at[s][i] contém o offset daquele objeto dentro da seção combinada.

LdMap.total[s] contém o tamanho final combinado.

As quatro famílias de seção são empacotadas independentemente.

Isso produz offsets estáveis por objeto antes da atribuição dos endereços virtuais e offsets de arquivo finais.

## Região de leitura e execução

Text e rodata são combinadas no lado executável/somente leitura da saída.

Se rodata existir, sua região combinada começa após text alinhada em 16 bytes:

    ro_off = align_up(total_text, 16)

O tamanho de arquivo da região RX fica:

    rx_filesz = text_total + alinhamento opcional + rodata_total

Text começa em load_addr na memória virtual.

Rodata segue em load_addr + ro_off.

É uma política mais simples que um linker script completo, mas preserva uma fronteira significativa de permissões entre código/dados.

## Região gravável

Se data ou BSS for não vazia, ChrisLd emite um segmento gravável separado.

O tamanho em memória de RX é arredondado para fronteira de página de 4 KiB.

O endereço virtual gravável passa a ser:

    rw_vaddr = load_addr + rx_memsz

Dentro da região gravável:

- data inicializada vem primeiro;
- BSS vem depois.

O endereço de símbolo de BSS é calculado como:

    rw_vaddr
      + total_data
      + offset_bss_do_objeto
      + offset_do_simbolo

BSS contribui para o tamanho em memória, mas não para o tamanho do arquivo.

É a ideia padrão de armazenamento zerado além dos bytes inicializados, implementada no layout compacto do projeto.

## Saídas com um ou dois segmentos

ChrisLd possui dois modos de layout.

Para programa contendo apenas text/rodata, escreve um único PT_LOAD com permissões de leitura e execução.

Se houver data ou BSS, escreve dois PT_LOAD:

| Segmento | Conteúdo | Flags |
| --- | --- | --- |
| RX | text + rodata | PF_R | PF_X |
| RW | data + BSS | PF_R | PF_W |

Ele não emite intencionalmente um PT_LOAD simultaneamente gravável e executável.

chrisld_validate rejeita explicitamente segmento de carga cujas flags contenham W e X.

A separação W^X é uma das propriedades de segurança mais importantes do desenho atual.

## Política do cabeçalho ELF

A saída é ELF64, little-endian, System V ABI, ET_EXEC, EM_X86_64.

ChrisLd grava diretamente os campos do ELF header.

Constantes atuais incluem:

- tamanho do ELF header: 64 bytes;
- tamanho de program header: 56 bytes;
- um ou dois program headers;
- alinhamento de página: 4096 bytes.

Não é emitida uma section-header table.

A saída é, portanto, orientada ao loader, e não um ELF rico destinado a ferramentas genéricas de pós-link.

Isso é suficiente para uma imagem executável cujo loader depende principalmente dos program headers.

## Posicionamento no arquivo

Na saída de um segmento, bytes RX começam depois do ELF header e de um program header, alinhados em 16 bytes.

Quando há estado gravável, a implementação posiciona o payload RX num offset de arquivo orientado a página, derivado do page offset do load address.

Os bytes RW de data, quando existem, aparecem após o intervalo correspondente ao tamanho em memória de RX.

BSS não recebe bytes no arquivo.

O mapeamento foi desenhado para que os PT_LOAD descrevam intervalos virtuais coerentes com permissões distintas.

## Seleção do entry point

ChrisLd procura símbolos definidos para escolher o ponto de entrada.

A prioridade é:

1. kstart;
2. main;
3. o load address fornecido caso nenhum exista.

O primeiro kstart definido encontrado é escolhido.

Somente quando não existe kstart o linker procura main.

Isso corresponde à distinção entre a convenção de entrada nativa do kernel e programas/testes mais simples.

O linker não exige atualmente que kstart ou main exista. Assim, o chamador pode receber um ELF cujo entry permanece igual ao endereço base.

chrisld_validate posteriormente exige que o entry selecionado esteja dentro de um PT_LOAD executável.

## Endereços finais dos símbolos

sym_addr converte um símbolo ChrisO relativo ao objeto em endereço virtual final.

Símbolos de text usam load_addr mais o offset empacotado de text do objeto.

Símbolos de rodata adicionam ro_off.

Símbolos de data usam rw_vaddr mais o offset empacotado de data.

Símbolos de BSS usam rw_vaddr mais o tamanho total de data, o offset empacotado de BSS e o offset do símbolo.

A função é central para relocations porque cada relocation precisa do endereço final do símbolo resolvido.

## Mapeamento do local da relocation

reloc_site converte a localização ChrisO da relocation em duas coordenadas:

- file_at: posição do campo no buffer do arquivo de saída;
- place: endereço virtual runtime daquele campo.

São suportados campos de relocation em text, rodata e data.

Uma relocation cujo campo a corrigir esteja em BSS é rejeitada porque BSS não possui bytes no arquivo para serem alterados.

A distinção deriva diretamente do modelo de BSS.

## Fórmulas de relocation

apply_one implementa os tipos suportados.

Para R_X86_64_64:

    resultado = S + A

e escreve oito bytes.

Para R_X86_64_PC32 e R_X86_64_PLT32:

    resultado = S + A - P

onde S é o endereço do símbolo, A o addend signed e P o endereço runtime do campo da relocation.

O resultado precisa caber em signed 32 bits.

Para R_X86_64_32 e R_X86_64_32S, a implementação atual calcula S + A e exige que o valor unsigned resultante não exceda 0xffffffff.

Isso significa que o tratamento atual de R_X86_64_32S não aplica de forma independente o intervalo signed de 32 bits normalmente associado a esse nome de relocation ELF. Ele compartilha o teste de limite superior de R_X86_64_32.

Esse comportamento deve ser tratado como contrato atual do ChrisLd, não como semântica completa de ELF.

Tipo de relocation não suportado faz o link falhar.

## Verificações de segurança das relocations

Para cada relocation, ChrisLd primeiro confirma que sym_index está dentro da tabela de símbolos do objeto de origem.

Depois resolve o símbolo, mapeia o local da relocation e verifica a largura da escrita contra o tamanho do arquivo produzido.

Overflow do displacement PC-relative é rejeitado.

Essas verificações evitam várias classes de truncagem silenciosa.

Entretanto, o linker confia em outras partes da ChrisoImage mais do que um parser de objetos endurecido confiaria. Por exemplo, não executa uma etapa completa e independente que valide antecipadamente cada índice de seção e cada offset de símbolo.

Objetos ChrisO atuais são esperados como produtos de ferramentas controladas pelo projeto.

## Validador ELF

chrisld_validate verifica:

- entrada não nula;
- pelo menos 64 bytes de ELF header;
- ELF magic;
- classe 64 bits;
- little endian;
- machine ID x86-64;
- tamanho esperado de program-header entry;
- pelo menos um program header;
- cada program header inspecionado dentro da entrada fornecida;
- filesz não maior que memsz em PT_LOAD;
- ausência de PT_LOAD simultaneamente gravável e executável;
- ausência de sobreposição entre intervalos virtuais PT_LOAD;
- entry point dentro de PT_LOAD executável.

Isso fornece evidência executável útil para o contrato da saída do linker.

## Limitações do validador

chrisld_validate é intencionalmente incompleto como verificador ELF genérico.

A implementação atual não valida integralmente, entre outros pontos:

- tipo ET_EXEC;
- campos de versão ELF e OSABI;
- p_offset + p_filesz dentro do arquivo fornecido;
- consistência de p_align;
- congruência entre offsets de arquivo e endereços virtuais;
- aritmética de ranges totalmente segura contra overflow em toda entrada malformada;
- section headers, porque o linker não os produz.

Ela também reduz e_phoff para um offset local de 32 bits ao percorrer os program headers.

A função deve ser entendida como sanity check das saídas do projeto, e não como fronteira de segurança para ELF arbitrário não confiável.

## Evidência de validação

tools/test_chrisld.c cobre contratos relevantes.

O primeiro teste monta uma função main, faz o link em endereço high-half, verifica o magic ELF, verifica que uma imagem somente de text tem um PT_LOAD e executa chrisld_validate.

O teste multiobjeto cria um caller contendo call foo e outro objeto que define foo.

Ele verifica que:

- link de múltiplos objetos funciona;
- relocation da call externa é resolvida para o displacement esperado;
- link do caller isolado falha porque foo permanece indefinido;
- duas definições globais de foo são rejeitadas.

Outro teste cria text, rodata e BSS.

Ele confirma que:

- rodata e BSS sobrevivem à montagem;
- o ELF ligado possui dois PT_LOAD;
- o segundo segmento é read/write e não executável;
- memória gravável começa na fronteira de página esperada;
- referência RIP-relative a BSS é relocada corretamente;
- bytes de rodata aparecem na posição esperada.

Esses testes fornecem evidência concreta para resolução de símbolos, relocations, layout de seções e segmentação W^X.

Eles não comprovam todos os tipos de relocation suportados nem todos os caminhos de entrada malformada.

## Integração in-kernel

kernel/tools/native_link.c aloca buffer temporário de um MiB, chama chrisld_link em NATIVE_USER_LOAD, escreve o ELF em ChrisFS e libera o buffer.

É um consumidor real do linker dentro do kernel.

kernel/tools/chrisbuild.c também chama ChrisLd nos experimentos de build interno do kernel.

A etapa atual de combinação de objetos desse builder é mais limitada que o próprio ChrisLd porque ele combina unidades de compilação usando chriso_merge_text antes do link final.

Esse helper combina apenas text e tabelas relacionadas sob contrato estreito.

Assim, a existência de chrisld_link_objects não deve ser usada para afirmar que o builder interno atual já reproduz o link completo de produção.

## Relação com o linker script de produção

ChrisLd utiliza uma política compacta e hard-coded de layout.

O build normal do kernel de produção possui contrato de linker script mais rico, incluindo posicionamento real das seções do kernel e requisitos de boot.

O linker nativo experimental demonstra mecanismos reais de executable linking, resolução de símbolos e segmentos com permissões separadas, mas ainda não é substituto direto para todos os detalhes do link de produção.

Essa distinção é especialmente importante nas afirmações sobre self-hosting.

## Complexidade

Considere O como quantidade de objetos, S como total de símbolos, R como total de relocations e B como total de bytes de seções copiados.

Empacotamento e cópia de seções são aproximadamente O(O + B).

A iteração das relocations é O(R), mas cada resolução de símbolo global pode percorrer símbolos em todos os objetos, dando custo proporcional a S por referência global/indefinida.

A detecção de globais duplicados também usa scans aninhados.

A implementação é adequada para conjuntos pequenos e fixos de objetos.

Um linker maior normalmente construiria mapas indexados de símbolos e separaria validação em fases explícitas.

## Comportamento de falhas

O linker retorna -1 para falhas estruturais ou semânticas, incluindo:

- argumentos inválidos;
- mais de 32 objetos;
- definições globais duplicadas;
- ausência de conteúdo ligável;
- capacidade de saída insuficiente;
- sym_index inválido;
- símbolo não resolvido ou ambíguo;
- seção de relocation não suportada;
- tipo de relocation não suportado;
- escrita de relocation fora do arquivo gerado;
- overflow do range PC-relative.

Ainda não existe estrutura pública detalhada de diagnóstico do linker.

O chamador recebe comprimento de sucesso ou falha.

## Limitações atuais

As principais fronteiras atuais são:

- máximo de 32 objetos por link multiobjeto direto;
- capacidades fixas de símbolos e relocations do ChrisO;
- resolução simples O(S) por símbolo;
- detecção quadrática de globais duplicados;
- ausência de weak symbols;
- ausência de archives e extração lazy;
- ausência de dynamic linking;
- ausência de construção GOT/PLT além da aplicação da relocation PLT32 do projeto;
- ausência de TLS;
- ausência de section headers;
- ausência de linker script arbitrário;
- ausência de dead-section elimination;
- ausência de identical-code folding;
- ausência de LTO;
- validação incompleta de objetos/ELF hostis;
- semântica simplificada de R_X86_64_32S;
- ausência de diagnósticos ricos.

Essas restrições definem o perfil experimental do linker.

## Limite entre estado atual e roadmap

Evoluções naturais incluem:

- tabelas indexadas de símbolos globais;
- fase explícita de validação de todos os campos ChrisO;
- diagnósticos estruturados;
- verificações mais fortes de overflow;
- semântica signed exata para R_X86_64_32S;
- metadados gerais de alinhamento de seções;
- conceitos compatíveis com o linker script de produção;
- mais famílias de relocation;
- conjuntos de objetos maiores ou dinâmicos;
- metadados de debug;
- link maps determinísticos;
- evidência mais forte de reprodutibilidade.

Esses itens são direções futuras, não garantias atuais.

## Proveniência da revisão

Este capítulo documenta ChrisLd conforme observado no main do ChrisOS na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

A autoridade de implementação é compiler/chrisld/chrisld.c e compiler/chrisld/chrisld.h. O contrato dos objetos de entrada vem de compiler/chrisld/chriso.h. tools/test_chrisld.c fornece evidência host executável direta. kernel/tools/native_link.c e kernel/tools/chrisbuild.c demonstram as fronteiras atuais de integração in-kernel.
