---
id: home
lang: pt-br
type: landing
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - README.md
  - kernel/metal/start.c
  - chrisvm/chrisvm.h
---

# Projeto de Pesquisa ChrisOS

<div class="record">
<span>Branch de fonte: <b>main</b></span>
<span>Baseline documental: <code>da3df29cb397</code></span>
<span>Modelo: static / revision-bound</span>
</div>

<div class="abstract">
<b>Resumo.</b> ChrisOS é um ecossistema experimental de sistemas operacionais que reúne um kernel higher-half x86-64, ChrisC e CLVM, um caminho nativo de compilador/assembler/linker, ChrisFS, desktop gráfico, renderização por software e gráficos paravirtuais, além do emulador ChrisVM/ChrisCPU. Esta documentação constrói os pré-requisitos desde os fundamentos físicos da computação e os conecta à implementação concreta existente na branch main.
</div>

<figure class="figure">
<img src="../assets/diagrams/system-layers.svg" alt="Camadas da computação">
<figcaption>A sequência conceitual vai da matéria às aplicações; cada camada introduz apenas mecanismos já fundamentados nas anteriores.</figcaption>
</figure>

## Percurso de aprendizado

[Iniciar a sequência de 12 níveis](learning-path.md): matéria, representação, arquitetura, boot, kernel, linguagens, armazenamento, pixels, gráficos, redes, máquinas virtuais e pesquisa. O catálogo mostra os pré-requisitos e as lacunas de cada capítulo.

## Estrutura da obra

A obra separa teoria, arquitetura, implementação, validação, limitações e roadmap. Uma funcionalidade não é tratada como comprovada apenas porque há código. O Atlas de Fonte é gerado mecanicamente; os capítulos autorais explicam significado, invariantes, ownership, concorrência, falhas e relação entre subsistemas.

<figure class="figure">
<img src="../assets/diagrams/chrisos-overview.svg" alt="Visão geral do ChrisOS">
<figcaption>Organização de alto nível do ecossistema atual.</figcaption>
</figure>

## Coleções

| Volume | Escopo |
|---|---|
| [01-foundations — Fundamentos físicos e digitais](01-foundations/index.md) | Matéria, carga elétrica, dispositivos semicondutores, MOSFETs, lógica CMOS, álgebra booleana e circuitos combinacionais e sequenciais. |
| [02-computer-architecture — Arquitetura de computadores](02-computer-architecture/index.md) | Datapaths, controle, conjuntos de instruções, execução x86-64, privilégio, caches, hierarquia de memória, barramentos, MMIO e DMA. |
| [03-boot — Boot e formatos executáveis](03-boot/index.md) | Estado após energização, firmware, UEFI, Limine, carregamento ELF, layout de linkedição e transição para o entry point do ChrisOS. |
| [04-kernel — Arquitetura do kernel](04-kernel/index.md) | Fronteiras de privilégio, organização monolítica modular, exceções, interrupções, SMP, processos, execução ELF em user mode e syscalls. |
| [05-memory — Sistemas de memória](05-memory/index.md) | Alocação de memória física, endereçamento virtual, paginação de quatro níveis, CR3, TLBs, heaps, ownership e invalidação multiprocessador. |
| [06-storage — Armazenamento e filesystems](06-storage/index.md) | Block devices, conceitos ATA/AHCI/NVMe/VirtIO, setores, DMA, estruturas de filesystem, journal, ChrisFS e instalação. |
| [07-language-systems — Linguagens e toolchains](07-language-systems/index.md) | Análise léxica, parsing, semântica, representações intermediárias, bytecode, JIT e os caminhos ChrisC/toolchain nativo. |
| [08-graphics — Sistemas gráficos](08-graphics/index.md) | Pixels, cor, framebuffers, scanout, composição, rasterização, depth, VirtIO-GPU, VirGL e shaders programáveis. |
| [09-emulation — Emulação de máquina e virtualização](09-emulation/index.md) | Interpretação de instruções, estado arquitetural, buses e dispositivos, ChrisVM/ChrisCPU e a fronteira para virtualização assistida por hardware. |
| [10-networking — Rede](10-networking/index.md) | Interfaces de rede, movimentação de pacotes, conceitos Ethernet/IP/UDP/TCP e os caminhos de rede VirtIO atuais. |
| [11-desktop — Desktop e aplicações](11-desktop/index.md) | Gerenciamento de janelas, composição, roteamento de entrada, aplicações ChrisC e workloads do sistema. |
| [12-self-hosting — Self-hosting e bootstrap](12-self-hosting/index.md) | Bootstrap de compiladores, objetos e executáveis produzidos internamente, marcos de rebuild do kernel e redução de dependências. |
| [13-real-hardware — Instalação e hardware real](13-real-hardware/index.md) | GPT, ESP, mídia UEFI, perfis de hardware, evidência de drivers e a distinção entre emulação e suporte em máquina física. |
| [14-validation — Validação e confiabilidade](14-validation/index.md) | Testes host, gates QEMU, evidência em hardware físico, invariantes, contenção de falhas, auditoria de estabilidade e reprodutibilidade. |
| [15-specifications — Especificações e formatos](15-specifications/index.md) | Contratos ChrisVM, ChrisO, protocolos de boot, formatos de filesystem, ABIs, protocolos gráficos e especificações externas. |
| [16-history — História da arquitetura](16-history/index.md) | Histórico vinculado a revisões das mudanças arquiteturais, designs substituídos e razões para mudanças de interface. |

## Política de evidência

1. Código atual em main.
2. Testes e gates reproduzíveis na mesma revisão.
3. Especificações atuais mantidas no repositório.
4. Auditorias históricas, identificadas pela revisão a que pertencem.
5. Roadmap explicitamente marcado como futuro.
