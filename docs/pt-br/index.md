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
<span>Modelo de publicação: static / revision-bound</span>
</div>

<div class="abstract">
<b>Resumo.</b> ChrisOS é um ecossistema experimental de sistemas que contém kernel x86-64, ChrisC e CLVM, componentes nativos de compilador/assembler/linker, ChrisFS, subsistemas gráficos e de desktop, rede e a pilha de emulação ChrisVM/ChrisCPU. A documentação é organizada como corpus técnico ordenado por dependências, dos fundamentos físicos à pesquisa em sistemas operacionais.
</div>

## Organização canônica

A documentação possui duas camadas organizacionais independentes:

| Camada | Finalidade | Autoridade |
|---|---|---|
| currículo de aprendizado | define pré-requisitos e progressão conceitual | data/curriculum.yml |
| coleções do repositório | mantém caminhos estáveis e agrupamento temático | docs/en/* e docs/pt-br/* |

O currículo é a autoridade para a ordem de leitura. A numeração dos diretórios permanece por estabilidade de URLs e manutenção do repositório; ela não substitui a ordem de pré-requisitos.

[Percurso de aprendizado e lacunas atuais](learning-path.md)

## Cadeia de dependências

<figure class="figure">
<img src="../assets/diagrams/system-layers.svg" alt="Camadas da computação">
<figcaption>Cada camada é definida somente após os mecanismos exigidos pelas camadas anteriores.</figcaption>
</figure>

A cadeia principal é:

~~~text
matéria e modelos físicos
    ↓
ferramentas matemáticas exigidas pelo modelo físico
    ↓
campos elétricos, circuitos e comportamento eletromagnético
    ↓
dispositivos semicondutores e CMOS
    ↓
lógica booleana e sequencial
    ↓
representação, estruturas de dados e algoritmos
    ↓
arquitetura de CPU e interfaces de plataforma
    ↓
firmware e boot
    ↓
kernel, memória, concorrência e processos
    ↓
linguagens e armazenamento persistente
    ↓
gráficos, rede e desktop
    ↓
emulação, virtualização e self-hosting
    ↓
hardware real, validação e especificações
~~~

Capítulos ausentes permanecem visíveis no currículo e não são ignorados pela sequência canônica de anterior/próximo.

## Níveis do currículo

| Nível | Escopo técnico |
|---|---|
| 01 · Matéria, ferramentas matemáticas, eletricidade, dispositivos e lógica | matéria, eletrostática, circuitos, semicondutores, CMOS, lógica booleana, circuitos aritméticos, estado e células de memória |
| 02 · Representação e algoritmos | matemática discreta, representação binária, complexidade, estruturas de dados e algoritmos de sistemas |
| 03 · Execução de instruções e plataforma | datapaths, microarquitetura, ISA, x86-64, hierarquia de memória, PCIe, MMIO, DMA e ACPI |
| 04 · Do reset à entrada do kernel | reset, firmware, UEFI, Limine, ELF, linkedição e entrada higher-half |
| 05 · Kernel, memória e contextos de execução | trust boundaries, exceções, PMM, paginação, TLBs, concorrência, user mode e ciclo de processos |
| 06 · Linguagens, compiladores e runtimes | construção de compiladores, ChrisC, CLVM, JIT e toolchain nativo |
| 07 · Estado persistente e filesystems | block storage, ATA/AHCI/NVMe/VirtIO e estruturas/recuperação do ChrisFS |
| 08 · Dos bytes ao desktop | framebuffer, gráficos 2D, composição, input, janelas e aplicações |
| 09 · Geometria, rasterização e GPUs | transformações, rasterização, VirtIO-GPU, VirGL e shaders |
| 10 · Redes e estados de protocolo | Ethernet, IPv4, UDP, TCP, VirtIO-net e sockets |
| 11 · Emulação e virtualização | emulação x86, ChrisVM/ChrisCPU, VMX/SVM e tradução de segundo nível |
| 12 · Bootstrap, validação e pesquisa | self-hosting, hardware real, validação, especificações, história e manutenção do corpus |

## Estrutura dos documentos

Capítulos técnicos separam as seguintes classes de evidência:

1. teoria física ou matemática;
2. arquitetura geral de sistemas;
3. implementação atual do ChrisOS/ChrisCPU;
4. validação executável ou evidência derivada do source;
5. limitações conhecidas;
6. arquitetura futura explicitamente identificada como futura.

A existência de um símbolo no source não comprova conclusão de funcionalidade. Afirmações de implementação permanecem vinculadas à revisão analisada.

## Semântica de navegação

Cada capítulo curricular expõe:

- nível e módulo;
- posição absoluta na sequência;
- capítulos planejados anterior e seguinte;
- pré-requisitos técnicos declarados;
- capítulos autorais que dependem dele;
- par de idiomas;
- revisão e arquivos de source.

Quando o item anterior ou seguinte está ausente, a lacuna aparece explicitamente em vez de ser ignorada.

## Coleções do repositório

As coleções estáveis permanecem disponíveis para consulta temática:

| Coleção | Assunto |
|---|---|
| [Fundamentos](01-foundations/index.md) | pré-requisitos físicos, elétricos, digitais, matemáticos e algorítmicos |
| [Arquitetura de computadores](02-computer-architecture/index.md) | CPU, x86-64, hierarquia de memória e plataforma |
| [Boot](03-boot/index.md) | firmware, layout executável e entrada do kernel |
| [Kernel](04-kernel/index.md) | execução privilegiada, interrupts, processos e modelo de kernel |
| [Memória](05-memory/index.md) | memória física/virtual, TLBs, alocação e lifetime |
| [Armazenamento](06-storage/index.md) | block devices e filesystems |
| [Sistemas de linguagens](07-language-systems/index.md) | compiladores, runtimes e toolchain nativo |
| [Gráficos](08-graphics/index.md) | framebuffer, gráficos 2D/3D e interfaces de GPU |
| [Emulação](09-emulation/index.md) | ChrisVM, ChrisCPU e virtualização |
| [Rede](10-networking/index.md) | protocolos e dispositivos de rede |
| [Desktop](11-desktop/index.md) | janelas, input e aplicações |
| [Self-hosting](12-self-hosting/index.md) | bootstrap e rebuild interno |
| [Hardware real](13-real-hardware/index.md) | instalação, bring-up e compatibilidade |
| [Validação](14-validation/index.md) | testes, gates, faults e medições |
| [Especificações](15-specifications/index.md) | formatos, ABIs e contratos de protocolo |
| [História da arquitetura](16-history/index.md) | histórico arquitetural vinculado a revisões |

## Política de evidência

1. Source atual em main.
2. Checks e gates reproduzíveis contra a mesma revisão.
3. Especificações atuais mantidas no repositório.
4. Material histórico explicitamente vinculado à revisão correspondente.
5. Trabalho futuro separado do comportamento implementado.
