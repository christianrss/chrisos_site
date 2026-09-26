---
id: power-on-kstart
lang: pt-br
type: technical-chapter
volume: 03-boot
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/start.c
  - kernel/metal/bootinfo.c
  - kernel/metal/linker.ld
symbols:
  - kstart
depends_on:
  - x86-64-memory-privilege
related:
  - elf-linking
  - kernel-model
---

# Da energização a `kstart`

## Reset não é uma chamada de função C

Quando uma máquina física liga ou sofre reset, o processador começa em um estado definido pela arquitetura. Ele não conhece ChrisOS, C, símbolos ELF nem a stack do kernel. O firmware da plataforma estabelece estado suficiente para localizar e iniciar um alvo de boot.

PCs modernos normalmente usam UEFI. BIOS legado segue caminho histórico diferente. ChrisOS atualmente utiliza Limine como bootloader externo em vez de implementar descoberta de firmware.

## Responsabilidades por camada

```text
power/reset
   ↓
estado de reset da CPU
   ↓
firmware
   ↓
boot manager / bootloader
   ↓
imagem ELF do kernel
   ↓
informações do protocolo Limine
   ↓
kstart
   ↓
inicialização ChrisOS
```

Cada camada remove responsabilidades da próxima.

## Imagem executável

O kernel é um ELF64 produzido segundo `kernel/metal/linker.ld`. O script declara `ENTRY(kstart)` e organiza program headers e seções para que o loader posicione a imagem corretamente.

O identificador C `kstart` torna-se parte de um contrato binário: o linker grava seu endereço resolvido como entry point do ELF.

## Higher-half

ChrisOS é linkado em região virtual alta. Os endereços usados pelo código compilado não são simplesmente endereços físicos baixos.

O bootloader precisa estabelecer ou cooperar com mapeamentos que tornem esses endereços virtuais válidos antes de entregar o controle. Por isso um loader que apenas copia bytes e salta para o começo do arquivo não é suficiente.

## Informações de boot

O kernel precisa de fatos da máquina que não podem ser compilados na imagem:

- memory map;
- descrição do framebuffer;
- higher-half direct map;
- informações de CPUs/SMP;
- configuração e respostas do protocolo.

`kernel/metal/bootinfo.c` concentra a interpretação dos dados do Limine. Essas respostas devem ser validadas porque allocators e drivers posteriores dependem delas.

## Ordem de `kstart`

`kernel/metal/start.c` contém a principal sequência arquitetural. Ordem de inicialização não é estética; cada subsistema exige invariantes estabelecidas antes.

Na revisão documentada aparecem serial/build info, processamento de boot, fundamentos de descritores/interrupções, memória física e virtual, heap/processos, gráficos, SMP/APIC, ACPI/storage/filesystem, runtime de linguagem, desktop e rede.

<figure class="figure">
<img src="../../../assets/diagrams/boot.svg" alt="Fluxo de boot ChrisOS">
<figcaption>Principais estágios de inicialização. A ordem exata do código é autoritativa para uma revisão específica.</figcaption>
</figure>

## Serial precoce

Desktop gráfico não pode diagnosticar falhas ocorridas antes dos gráficos. Serial é inicializada cedo para que o caminho de diagnóstico dependa de menos componentes que aqueles que ele precisa observar.

## Estado de interrupções

Inicialização precoce normalmente ocorre com interrupções mascaráveis desabilitadas porque handlers, stacks, roteamento e estado global podem não estar prontos. Habilitar interrupções é um marco: código assíncrono passa a poder executar entre instruções comuns.

Locks e estruturas acessíveis por IRQ precisam ter seus contratos de concorrência estabelecidos antes disso.

## Bootloader e self-hosting

Self-hosting do compilador do kernel não implica remover Limine. São dependências diferentes.

Self-hosted kernel build pergunta se ChrisOS consegue produzir seu próprio executável. Bootloader próprio pergunta se o projeto substitui o programa que carrega esse executável. O primeiro pode ser atingido mantendo o segundo externo.

## Contraste com ChrisVM

O boot protocol v1 do ChrisVM começa muito mais tarde: prepara ambiente 64-bit, page tables iniciais e um contrato pequeno de máquina diretamente. Nesse marco não há BIOS ou UEFI emulados.

Isso mostra que um emulador pode definir uma plataforma virtual com protocolo de boot específico, enquanto um kernel de PC depende dos contratos de firmware e bootloader disponíveis na plataforma.
