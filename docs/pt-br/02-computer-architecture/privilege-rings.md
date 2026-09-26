---
id: privilege-rings
lang: pt-br
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/gdt.c
  - kernel/metal/gdt.h
  - kernel/metal/idt.c
  - kernel/metal/idt_stubs.asm
  - kernel/metal/irq.c
  - kernel/metal/irq.h
  - kernel/metal/user_enter.c
  - kernel/metal/syscall.c
  - kernel/metal/proc.c
  - chrisvm/cpu/common/exceptions.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/cpu/emulator/mmu.c
symbols:
  - gdt_init
  - idt_set_user_gate
  - enter_user
  - irq_dispatch
  - syscall_dispatch
  - user_span_ok
  - user_copy
  - panic_user_fault
  - deliver_frame
  - chris_seg_load_cs
depends_on:
  - x86-64-memory-privilege
related:
  - kernel-model
  - processes-syscalls
  - idt-exceptions
---

# Anéis de privilégio, entrada controlada e fronteiras de proteção

## Privilégio é uma propriedade da execução

Um sistema operacional precisa permitir que código não confiável calcule valores sem conceder controle arbitrário sobre tradução de memória, interrupções ou dispositivos. Os mecanismos de privilégio separam essas autoridades. x86 identifica níveis de zero a três, com números menores indicando maior privilégio. Os caminhos do ChrisOS examinados aqui usam papéis de kernel e usuário convencionalmente associados a zero e três. Um número de privilégio não é um tipo da linguagem-fonte nem uma propriedade adquirida por chamar uma função de `kernel`.

CPL, nível de privilégio atual, descreve o contexto executando. DPL pertence a descritor ou gate. RPL ocupa os dois bits inferiores de um seletor. As comparações dependem da operação. Reduzir todas as regras a “o número menor vence” é insuficiente: acessar segmento de dados, invocar gate de interrupção e retornar a código menos privilegiado exigem verificações e transições diferentes.

Paginação fornece outra parte da fronteira. Uma instrução de usuário não pode acessar mapeamento de supervisor apenas por conhecer seu endereço. Por outro lado, entrar no kernel não demonstra que um endereço fornecido pelo usuário pode ser desreferenciado com segurança. O capítulo de memória explica permissões ao longo das tabelas. Este acompanha a entrada controlada e as verificações de software ainda necessárias depois que o hardware selecionou um handler autorizado.

## Seletores são referências, não endereços brutos de código

Um seletor contém índice de descritor, bit de seleção de tabela e RPL. Quando seleciona GDT, deslocá-lo três bits à direita fornece índice de slot de oito bytes. ChrisOS define código de kernel em `0x08`, dados de kernel em `0x10`, dados de usuário em `0x18`, código de usuário em `0x20` e TSS em `0x28`. A entrada de usuário aplica OR com três aos seletores correspondentes, produzindo CS `0x23` e SS `0x1b`.

| Componente do seletor | Finalidade | Exemplo |
|---|---|---|
| Índice | Localizar slot do descritor | `0x20 >> 3` seleciona slot quatro |
| Bit de tabela | Escolher GDT ou LDT | Zero nos seletores configurados |
| RPL | Contexto de privilégio solicitado | Bits inferiores três para usuário |

O descritor da GDT fornece atributos de acesso. Código em modo longo ainda depende de descritores válidos, embora endereçamento comum use um espaço essencialmente plano. O descritor TSS ocupa dois slots porque sua base precisa de bits altos adicionais. `install_tss_descriptor` constrói esses campos explicitamente; interpretar o segundo slot como segmento independente corromperia a referência à TSS.

`gdt_init` estabelece tabela e TSS de 104 bytes, define ponteiro de pilha de ring zero e carrega TR. O deslocamento do mapa de E/S fica além da estrutura. São fatos de configuração, não prova de autorização correta de toda instrução de E/S em todos os backends. Execução hospedeira, emulada e um futuro backend virtualizado por hardware precisam de caminhos próprios para impor a mesma regra arquitetural.

## Entrada em modo usuário por quadro explícito de retorno

`enter_user` constrói quadro com SS, RSP de usuário, RFLAGS, CS e RIP de usuário, depois executa IRETQ. A ordem de empilhamento deixa RIP como primeiro elemento consumido. RFLAGS é inicializado como `0x202`, incluindo bit um fixo e IF. Isso seleciona ponto de entrada e pilha por transição arquitetural controlada, em vez de uma chamada C comum.

A função também registra endereço de retorno de kernel obtido por `__builtin_return_address(0)` usando `syscall_set_kernel_return`. Esse valor pertence ao esquema de retorno desta implementação. Não é contexto geral de processo salvo: não captura todos os registradores preservados entre chamadas, vida útil de pilha, espaço de endereços ou estado de escalonador. O chamador precisa ter preparado mapeamentos válidos de código e pilha de usuário. Um quadro com inteiros plausíveis não substitui esses pré-requisitos.

O ponteiro da TSS importa ao entrar em código de kernel vindo de código menos privilegiado. O processador não deve continuar colocando estado privilegiado na pilha não confiável do usuário. Pilhas de emergência selecionadas por IST podem tratar outros cenários, mas os gates configurados aqui usam IST zero. Não se pode deduzir a existência de pilha de emergência apenas porque a estrutura TSS reserva campos IST.

## Autoridade do gate e caminho de chamadas de sistema

![Entrada controlada, validação de ponteiros e retorno](../../assets/diagrams/privilege-boundary.svg)

O diagrama separa a fronteira arquitetural pretendida do caminho de validação em software. As limitações do emulador descritas adiante impedem interpretá-lo como afirmação de que toda verificação de gate já funciona em ChrisCPU.

Um gate IDT combina posição de destino, seletor de código, tipo, presença e DPL. ChrisOS constrói 256 gates, normalmente com atributo `0x8e`. `syscall_init` torna o vetor `0x80` invocável por usuário usando `idt_set_user_gate`, que define atributo `0xee`. A mudança permite invocação por software de usuário, mantendo o descritor de código do kernel como destino.

DPL do gate não solicita execução do handler nesse nível. Restringe quem pode invocá-lo pela instrução de software pertinente. Uma interrupção externa tem origem diferente de INT emitido por usuário; uma falta de página é evento arquitetural síncrono, não número de serviço escolhido pelo programa. Regras de classe de evento da CPU e decisões de despacho do kernel devem permanecer separadas.

O caminho inspecionado usa vetor `0x80`; não deduz suporte a SYSCALL a partir do nome de um MSR. Stubs assembly normalizam informações de vetor/erro, salvam registradores gerais e chamam `irq_dispatch`. Essa função identifica `0x80` antes do tratamento genérico e chama `syscall_dispatch`. O dispatcher lê o serviço em RAX salvo e argumentos no quadro de registradores.

## Organização do quadro é uma ABI entre assembly e C

A estrutura C `irq_frame` começa em R15 e segue pelos registradores salvos até RAX, depois vetor, erro, RIP, CS e RFLAGS. O comentário assembly registra vetor no deslocamento 120, erro em 128 e RIP em 136. Esses valores resultam de quinze slots gerais de oito bytes. Alterar a ordem de push sem alterar C reinterpretaria valores como registradores ou controles diferentes, mesmo se ambos os arquivos compilassem.

Os stubs limpam DF antes de entrar em C, salvam estado de ponto flutuante/SIMD por FXSAVE em armazenamento alinhado, alinham a pilha para chamar C e restauram o estado depois. Estabelecem condições de chamada além de preservar RAX. A estrutura não enumera todo campo final que o processador pode empilhar; seu prefixo declarado precisa ser interpretado junto com assembly e contexto da transição. Uma declaração C isolada não prova o formato completo para todo evento.

A revisão encontra ainda `frame->rip += 2` repetido nos retornos comuns de chamadas de sistema. INT normalmente salva endereço posterior à instrução, e o handler INT de ChrisCPU avança RIP explicitamente antes de provocar o evento. Os stubs e despacho inspecionados não subtraem dois visivelmente antes. Essa discrepância exige teste dirigido do endereço de retorno; não é resolvida supondo que todo RIP salvo aponta ao opcode que provocou a entrada. Este capítulo não afirma execução de tal teste convidado.

## Validação de faixas sem overflow aritmético

Um serviço que recebe ponteiro e tamanho precisa validar a faixa inteira, não apenas seu primeiro byte. Verificar `address + length <= limit` com aritmética sujeita a wraparound poderia permitir que entrada grande ultrapassasse o limite pretendido. `user_span_ok` compara tamanho com `limit - address` depois de verificar que o endereço está abaixo do limite. A subtração é segura porque a verificação anterior estabelece a ordem necessária.

O helper aceita primeiro faixas de tamanho zero. Para tamanho não nulo, rejeita endereços a partir de `0x0000800000000000`, rejeita faixas que ultrapassam essa fronteira, verifica intervalo de usuário configurado e rejeita tamanho maior que o restante desse intervalo. Inicialmente, o intervalo vai de `0x400000` a `0x500000`, excluindo o limite superior. Essa política é mais restrita que toda a metade canônica de usuário e pode mudar por `syscall_set_user_map`.

Limites são apenas uma camada. `user_copy` obtém CR3 do processo atual e percorre cada página por `mm_translate`. Exige flags de folha presente e de usuário; para copiar ao usuário, exige também escrita. Acessa o recurso físico pelo mapeamento direto da metade alta, em vez de desreferenciar diretamente o endereço virtual recebido. Mapeamentos ausentes retornam erro, evitando deliberadamente provocar falta de página em ring zero pela desreferência direta do ponteiro do usuário.

## Cópia, propriedade e concorrência

O laço escolhe cada trecho como o menor valor entre bytes restantes e bytes até a fronteira de página. Copia byte a byte e repete a tradução para a página seguinte. Para n bytes em p páginas, o trabalho local é O(n + p × h), com h representando profundidade limitada da caminhada, sem incluir contenção externa ou custos de dispositivos. O armazenamento temporário é constante; o chamador possui o buffer de kernel e valida sua capacidade pelas regras do serviço.

Verificar e copiar são operações separadas. O helper não fixa visivelmente o quadro traduzido por toda a operação nem mantém trava de tabela durante cada cópia. Segurança contra desmapeamento concorrente depende, portanto, de restrições mais amplas de execução e propriedade. A troca de processos confina explicitamente processos de usuário ao processador de bootstrap; o dispatcher rejeita chamadas em outra CPU. Essas restrições reduzem o modelo concorrente, mas não demonstram segurança de qualquer alteração concorrente dos mapeamentos.

Progresso parcial também importa. Se uma página posterior falha, trechos anteriores já foram copiados. Retornar erro não significa que o destino permaneceu inalterado. Serviços que exigem publicação integral precisam definir armazenamento provisório ou reversão. O comportamento é análogo ao acesso por trechos documentado no emulador, mas as funções operam em domínios diferentes e exigem revisões independentes.

## Autoridade específica de serviços e contenção de falhas

Em SYS_WRITE, o dispatcher aceita descritor um e até 80 bytes, copia para buffer local de 81 bytes e chama o helper de terminação antes da saída serial. O byte extra comporta o terminador no maior tamanho aceito. Verificar ponteiro não substitui verificar capacidade: a memória pode ser válida enquanto o destino é pequeno demais. Erros definem RAX salvo como −1; sucesso retorna a quantidade de bytes.

Handles semelhantes a arquivos usam uma pequena tabela `UFile` com estado de uso, processo proprietário e caminho. `ufile_owned` verifica faixa do descritor, estado ativo e identidade do proprietário. Isso mostra autoridade de objetos além de rings: dois processos no mesmo CPL não podem automaticamente usar handles um do outro. Fechar handles de um proprietário percorre a tabela limitada, com custo limitado por sua capacidade, não pelo tamanho arbitrário do sistema de arquivos.

Em falta de página, `irq_dispatch` primeiro consulta `proc_fault_demand` para verificar se o processo atual consegue resolvê-la. Caso contrário, examina bits de privilégio do CS salvo e encaminha faltas de usuário a `panic_user_fault`. Esse caminho registra a falta, destrói processo com identificador positivo, escreve contexto diagnóstico e prepara retorno ao kernel. Exceção restante de kernel segue para panic. É a ordem do despacho, não prova de contenção segura de toda solicitação malformada.

## Proteção emulada é uma obrigação de implementação separada

`deliver_frame` de ChrisCPU lê gate de dezesseis bytes, verifica presença e tipos suportados, rejeita IST não nulo, carrega seletor de código de destino e empilha quadro usando a pilha atual. O caminho não implementa toda a expectativa de transição de hardware do kernel: não apresenta troca de pilha pela TSS nem comparação de DPL do gate. `chris_seg_load_cs` verifica propriedades selecionadas do descritor, mas não atualiza CPL do modelo. IRETQ também carrega seletores sem reconciliar CPL visivelmente.

Isso importa porque a MMU determina acesso de usuário por `arch.cpl`, não apenas pelos bits inferiores do seletor CS armazenado. Um seletor que parece representar ring três não demonstra imposição de permissões de usuário nesse backend. MOVCR, MSR e CLI/STI também exigem verificações arquiteturais explícitas. Essas observações identificam lacunas; usar a instrução correta no kernel não corrige uma verificação ausente no emulador.

A validação precisa cobrir ambos os sentidos: transições autorizadas devem alcançar handler e estado de retorno corretos; operações não autorizadas devem falhar sem conceder autoridade nem corromper estado preservado. Sondas existentes de aritmética, decode e MMU fornecem evidência mais restrita, sem executar a transição completa. Casos convidados ainda necessários incluem escrita de usuário em página de supervisor, rejeição de instrução privilegiada, rejeição por DPL, troca de pilha, RIP de retorno e restauração de CPL. Até executá-los com sucesso, este capítulo documenta comportamento do fonte e obrigações abertas, sem certificar isolamento.
