---
id: chrisvm-boot
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/chrisvm.h
  - chrisvm/machine/boot.c
  - chrisvm/machine/machine.c
  - chrisvm/frontend/main.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - CHRIS_BOOT_PROTOCOL
  - chris_load_elf
  - chris_boot
  - install_tables
depends_on:
  - chrisvm-devices
  - chris-architecture-state
  - emulator-paging
  - elf-linking
related:
  - chrisvm-memory-map
  - chrisvm-debugger
  - boot-information
  - higher-half-kernel
---

# Protocolo de boot v1 do ChrisVM

## Escopo

O boot protocol v1 do ChrisVM é um handoff sintético para pequenos guests ELF x86-64. Ele não emula firmware nem reproduz a transição física da CPU desde reset, real mode e protected mode até long mode.

O protocolo executa três etapas principais:

1. carrega PT_LOAD aceitos em low guest RAM;
2. constrói um ambiente mínimo de long mode;
3. posiciona diretamente a CPU no entry point de 64 bits com stack predefinida.

Isso torna o ChrisVM útil como execution harness para guests controlados, mantendo BIOS, UEFI, Limine e o kernel higher-half completo fora da fronteira de compatibilidade atual.

A constante pública:

    CHRIS_BOOT_PROTOCOL = 1

identifica a versão atual, mas o código inspecionado não entrega esse número ao guest em uma estrutura de boot information.

Este capítulo documenta a revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Ciclo da frontend

A frontend executa:

    configuração
    -> leitura do ELF no host
    -> criação de ChrisMachine
    -> callbacks host de log/serial
    -> chris_load_elf
    -> chris_boot
    -> chris_run ou debug loop
    -> dump/view opcional do framebuffer
    -> destruição da máquina

Load e boot são operações separadas.

## Envelope ELF aceito

chris_load_elf exige:

- machine e image válidos;
- header Elf64Ehdr completo;
- ELF magic;
- classe ELF64;
- little-endian;
- e_machine igual a 62, x86-64;
- e_phentsize igual ao Elf64Phdr local;
- pelo menos um program header;
- program-header table inteira dentro do arquivo.

Somente PT_LOAD é copiado.

Outros program-header types são ignorados.

## Campos ELF não usados como gate

A implementação atual não valida ou usa semanticamente:

- e_type;
- e_version como política explícita;
- p_flags;
- p_paddr;
- p_align;
- section headers;
- relocation records;
- dynamic-linking metadata.

Logo, "ELF aceito" significa compatível com o loader estreito do ChrisVM, não conformidade geral com ELF.

## p_vaddr define o destino

Cada PT_LOAD é copiado para:

    machine RAM + p_vaddr

p_paddr é ignorado.

Assim, boot v1 é orientado a identidade: o virtual address do ELF também é o physical offset usado para carregar bytes.

As page tables iniciais identity-map RAM, fazendo o mesmo valor virtual alcançar esses bytes.

## Higher-half é rejeitado

PT_LOAD com p_vaddr em ou acima de:

    0xffff800000000000

é rejeitado com mensagem explícita de que higher-half está fora do boot protocol v1.

O entry point sofre a mesma restrição.

Portanto, o kernel ChrisOS higher-half normal não é carregado por esse protocolo.

Não existe special-case oculto para kstart ou relocation do kernel de produção.

## Limites dos segmentos

Para PT_LOAD:

    p_memsz >= p_filesz

é obrigatório.

O range dentro do arquivo precisa ser válido e o segmento precisa caber totalmente na guest RAM.

O check de memória usa subtração para evitar overflow de endereço final.

## Zero fill

Quando:

    p_memsz > p_filesz

a parte restante é zerada.

Isso implementa a expectativa de BSS do segmento carregável.

## Colisões com memória do boot

O loader rejeita overlap com:

- últimos CHRIS_PT_RESERVE bytes da RAM;
- página da GDT em CHRIS_GDT_PHYS;
- página de 4 KiB abaixo de CHRIS_STACK_RSP.

Essas regiões pertencem ao protocolo e não ao ELF.

Os checks são hard-coded, não derivados de um region registry central.

## Overlap entre PT_LOAD

Não há check de overlap entre segmentos PT_LOAD.

Eles são processados na ordem dos program headers.

Um segmento posterior pode sobrescrever bytes de um anterior.

Para ELF controlado isso pode não ocorrer, mas o loader não impõe a invariável.

## Falha tardia deixa load parcial

O carregamento não é transacional.

Se segmentos iniciais forem copiados e um segmento posterior falhar, chris_load_elf retorna erro sem rollback da RAM já modificada.

A frontend destrói a máquina nesse caso, então o caminho normal não reutiliza o estado.

A API de biblioteca, porém, não oferece garantia de rollback.

## Validação do entry point

Após os program headers, e_entry precisa:

- estar abaixo do limite higher-half v1;
- ser menor que ram_size.

Depois:

    machine->entry = e_entry

Não há verificação de que o entry:

- pertence a um PT_LOAD;
- está em segmento executável;
- aponta para bytes efetivamente carregados.

Como p_flags é ignorado, executable permission não faz parte do contrato do loader.

## Sem relocation ELF

O ELF é copiado exatamente no p_vaddr.

Não existe load bias nem processamento de relocations.

O guest precisa estar previamente linkado para o layout esperado pelo protocolo.

## Seleção de entry em chris_boot

chris_boot aceita entry explícito.

Se for zero, usa machine->entry proveniente do ELF.

O resultado final precisa ser diferente de zero e menor que ram_size.

Um host pode, portanto, substituir o entry do ELF por outro endereço low-RAM.

## Requisitos de RAM

Boot exige RAM:

- com pelo menos 2 MiB;
- múltipla de 2 MiB.

A machine layer já impõe os mesmos requisitos básicos.

A posição fixa do framebuffer limita a máquina criada normalmente a 32 MiB, mesmo que install_tables suporte conceitualmente mais.

## Reset antes do estado de boot

chris_boot chama:

    chris_arch_reset(&st)

zerando o estado e estabelecendo RFLAGS e baseline de CR0.

Depois constrói diretamente o ambiente sintético de long mode.

Não há transição instrução a instrução desde reset x86.

## Page tables

As quatro páginas finais de RAM são reservadas pelo protocolo.

install_tables coloca:

    PML4 = RAM_size - 0x4000
    PDPT = RAM_size - 0x3000
    PD   = RAM_size - 0x2000

Os primeiros 0x3000 bytes dessa reserva são zerados.

Depois:

    PML4[0] -> PDPT
    PDPT[0] -> PD

e RAM é mapeada em páginas de 2 MiB.

## Mapping inicial da RAM

Cada chunk de 2 MiB recebe:

    PDE[i] = physical_base | 0x83

com Present, Writable e Page Size.

O mapping é identidade.

Não há User bit.

O guest inicia em supervisor mode.

## Limite de um PD

pages é:

    ram_size / 2 MiB

e valores acima de 512 são rejeitados.

Logo, essa topologia representa no máximo 1 GiB por PDPT[0].

O limite prático atual de 32 MiB vem antes.

## Mapping do framebuffer

Se framebuffer existe, install_tables cobre seu range alinhado a 2 MiB usando PDEs do mesmo PD.

Antes de escrever, verifica se o slot está zero.

Isso evita substituir silenciosamente um mapping de RAM.

## GDT fixa

O protocolo grava três descriptors em:

    CHRIS_GDT_PHYS = 0x70000

São:

- null;
- code long mode;
- data.

GDTR aponta para esses 24 bytes.

A página inteira de 4 KiB fica reservada contra PT_LOAD.

## Segmentos iniciais

O estado recebe:

    CS = 0x08
    SS = 0x10
    DS = SS
    ES = SS

CS recebe base zero, limit 0xffffffff e attributes de long mode.

FS, GS, TR e LDTR continuam zerados.

Não há TSS criado pelo protocolo.

## Control state

install_tables define:

    CR0 = PE | NE | WP | PG
    CR3 = PML4
    CR4 = PAE
    EFER = LME | LMA

O estado é colocado diretamente na condição esperada para execução de 64 bits paginada.

O emulador não executa o processo real de entrada em long mode.

## Long mode é afirmado, não transitado

Em hardware físico, LMA emerge da combinação arquitetural correta; não é apenas um bit independente arbitrariamente gravável.

No protocolo v1, ChrisArchitectureState é um contrato sintético de início e LME/LMA são estabelecidos diretamente.

Isso é apropriado para um harness, mas não equivale a boot de CPU real.

## Privilege level inicial

O protocolo define:

    CPL = 0

Não há transição de ring no boot.

Nenhum contexto user é criado.

## RFLAGS inicial

RFLAGS recebe:

    2

IF começa limpo.

IRQ externo dependente de IF não é entregue até o guest habilitá-lo.

## Stack inicial

O padrão é:

    CHRIS_STACK_RSP = 0x80000

salvo quando o host passa rsp não zero.

A página imediatamente abaixo é reservada contra ELF loading.

Não existe guard page real nem metadata de stack entregue ao guest.

## Handoff ao backend

Depois de montar tables, GDT e registradores:

    backend->set_state(cpu, &st)

é chamado.

Em seguida:

    booted = 1
    entry = entry selecionado

ChrisCPU copia a estrutura inteira.

ChrisHV ainda não é funcional.

## Sem IDT

O protocolo não instala IDT nem configura IDTR.

IDTR permanece zero até o guest configurá-lo.

Nesse estado, faults são reportados ao monitor como CHRIS_EXIT_EXCEPTION, conforme o modelo atual de exceptions.

Isso ajuda diagnóstico de bring-up, mas não reproduz ambiente completo de firmware/OS.

## Sem TSS

Não há TSS nem TR carregado.

Consequentemente, não existem no boot v1:

- IST;
- stack switching de privilege;
- TSS I/O bitmap.

## Sem boot-information structure

O protocolo não cria estrutura guest-visible contendo:

- memory map;
- framebuffer descriptor;
- modules;
- command line;
- firmware tables;
- ACPI;
- CPU topology;
- protocol version.

O guest depende de constantes conhecidas ou de um ABI de teste próprio.

CHRIS_BOOT_PROTOCOL existe no source, não como handoff visível ao guest.

## Sem BIOS, UEFI ou Limine

Boot v1 não emula:

- BIOS;
- UEFI;
- UEFI memory map;
- PE/COFF loading;
- Limine requests/responses;
- boot modules;
- firmware graphics setup.

O ChrisOS de produção continua usando firmware + Limine.

ChrisVM v1 é outro caminho.

## Diferença para o kernel ChrisOS real

O kernel normal é higher-half e usa Limine.

O loader ChrisVM v1 rejeita exatamente esse layout.

Portanto, sucesso de guests de teste não prova que ChrisVM consegue iniciar o kernel de produção.

Para substituir QEMU nesse fluxo será necessário:

- ampliar o protocolo nativo;
- reproduzir o handoff esperado pelo kernel;
- implementar compatibilidade Limine;
- ou executar firmware/bootloader.

## NX não começa ativo

install_tables não define EFER.NXE.

Os PDEs iniciais também não distinguem code/data.

O guest pode habilitar NX posteriormente onde a MMU suporta.

O boot começa com mappings supervisor amplamente executáveis.

## p_flags não vira permission

Como p_flags é ignorado, PF_R/PF_W/PF_X não afeta as page tables.

RAM inicial é mapeada como writable supervisor large page.

Não há proteção ELF de segmento no boot v1.

## Falha na frontend

Se chris_load_elf ou chris_boot falha, a frontend:

- imprime erro;
- destrói a máquina;
- libera o buffer;
- retorna status 2.

chris_load_elf fornece mensagens detalhadas.

chris_boot apenas retorna sucesso/falha; se falhar sem mensagem do loader, a frontend pode imprimir o fallback genérico "entry".

Structured boot errors seriam melhores.

## Evidência de testes

test_chrisvm.c verifica:

- ELF válido;
- load e boot;
- execução até HLT;
- serial guest;
- bad magic;
- ELF truncado;
- framebuffer splash;
- faults depois do boot.

Também usa raw byte arrays em low RAM para testes menores.

Essa evidência é forte para o workflow v1 controlado, não para firmware compatibility.

## Gaps de validação ELF

Ainda faltam políticas explícitas para:

- e_type;
- e_version;
- exigir ao menos um PT_LOAD;
- overlap de PT_LOAD;
- entry dentro de segmento executável;
- p_align;
- p_flags em page permissions;
- política de p_paddr;
- rollback após falha parcial.

## Prioridades de hardening

Os próximos trabalhos de maior valor são:

1. criar boot-information versionado e visível ao guest;
2. entregar memory map e framebuffer explicitamente;
3. suportar o kernel higher-half real ou definir formalmente um ABI guest separado;
4. decidir entre protocolo nativo, handoff Limine-compatible ou execução real de bootloader;
5. endurecer validação ELF;
6. traduzir ELF permissions para paging;
7. tornar o load transacional;
8. retornar erros estruturados de chris_boot;
9. instalar ou delegar claramente IDT/TSS;
10. definir estado NX/security inicial;
11. mover endereços fixos para o machine map autoritativo;
12. testar evolução do protocolo e eventual higher-half.

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, o boot protocol v1 do ChrisVM é um handoff x86-64 sintético e deliberadamente restrito a low memory. Ele valida e copia um subconjunto ELF, identity-map RAM/framebuffer, instala GDT mínima e inicializa diretamente o estado de long mode. Não executa firmware, Limine ou a transição real da CPU, e rejeita intencionalmente o caminho higher-half do kernel ChrisOS de produção.
