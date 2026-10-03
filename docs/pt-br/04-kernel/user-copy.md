---
id: user-copy
lang: pt-br
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/syscall.c
  - kernel/metal/syscall.h
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/bootinfo.c
  - kernel/metal/irq.c
  - tools/test_sys_write.c
symbols:
  - user_span_ok
  - user_copy
  - copy_to_user
  - copy_from_user
  - mm_translate
  - translate_leaf
  - bootinfo_phys_to_virt
  - proc_cr3
depends_on:
  - virtual-memory
  - user-mode-entry
related:
  - processes-syscalls
  - page-faults
---

# Acesso seguro à memória de usuário

## Escopo

Um ponteiro vindo de user mode é um número controlado por um espaço não confiável. O kernel não pode convertê-lo em ponteiro C comum e desreferenciá-lo só porque o endereço parece plausível. A página pode estar ausente, supervisor-only, read-only, o buffer pode cruzar uma fronteira de página ou o processo pode já não possuir aquele mapeamento.

O ChrisOS implementa em `syscall.c` um caminho explícito de cópia. Ele valida a faixa declarada do ABI, traduz cada página usando o CR3 do processo atual, verifica flags e acessa o frame físico através do mapeamento do kernel. Página ausente retorna erro; a cópia em ring 0 não tenta demand paging automaticamente.

## Modelo de ameaça

O kernel deve considerar que um endereço fornecido por syscall pode:
- estar fora da faixa prevista;
- ser não canônico;
- provocar overflow quando combinado ao comprimento;
- apontar para página supervisor-only;
- apontar para página read-only em uma operação de escrita;
- atravessar páginas com permissões diferentes;
- estar não mapeado;
- tornar-se inválido se lifetime do processo não for protegida.

Por isso cada parte do span precisa ser provada.

## Faixa declarada

A camada mantém `g_user_map_lo` e `g_user_map_hi`, inicialmente `0x400000` e `0x500000`. `syscall_set_user_map` pode substituí-los.

`user_span_ok` aceita length zero. Para length não zero exige início abaixo de `0x0000800000000000`.

Antes de somar, testa:

```text
n <= 0x0000800000000000 - uaddr
```

Assim overflow unsigned é evitado pela própria forma da expressão.

Depois exige:
- `uaddr >= g_user_map_lo`;
- `uaddr < g_user_map_hi`;
- `n <= g_user_map_hi - uaddr`.

A última condição também evita calcular um end address potencialmente overflowado.

Isso prova somente a política de faixa. Ainda não prova page table.

## Por que range check não basta

Um buffer pode começar e terminar dentro da janela, mas atravessar uma página ausente. A segunda página pode ser supervisor-only. Um endereço pode traduzir e mesmo assim não permitir escrita.

Logo, ChrisOS faz range validation e translation/permission validation separadamente.

## Seleção do address space

`user_copy` obtém `proc_cr3(proc_current())` e rejeita CR3 zero.

A tradução usa explicitamente a raiz pertencente ao processo atual, em vez de presumir que um cast do endereço user no contexto do kernel seja seguro.

Hoje current process é global porque syscalls/process switching são BSP-only. Um modelo user SMP exigiria current task per-CPU/per-thread.

## Tradução página a página

A função mantém `done`. Para cada chunk calcula `addr = uaddr + done` e chama:

```c
mm_translate(cr3, addr, &phys, &flags)
```

Falha retorna -1.

Depois exige `MM_PRESENT` e `MM_USER`. Para copy-to-user exige também `MM_WRITE`.

Essa assimetria preserva write protection: ring 0 não deve usar seu privilégio para escrever em mapeamento user que o próprio processo vê como read-only.

## Comportamento do page walk

`mm_translate` entra na região crítica da MM e percorre recursivamente PML4, PDPT, PD e PT. Uma entrada não presente encerra a tradução com erro. O walker também reconhece huge pages nos níveis PDPT e PD; nesses casos calcula o endereço físico usando o offset correspondente ao tamanho da página e devolve como flags a entrada leaf efetivamente encontrada.

Mesmo quando a tradução termina em uma huge page, `user_copy` divide a transferência em fronteiras de 4 KiB. Isso é conservador: a política de permissão é reavaliada a cada segmento e o código não autoriza um span longo apenas porque o primeiro endereço traduziu corretamente.

O lock da MM protege a caminhada das page tables, não toda a transferência. Depois que `mm_translate` retorna, o lock já foi liberado e a cópia ocorre pelo HHDM. Portanto a validade do frame durante a cópia também depende do modelo de lifetime do processo.

## Buffers que cruzam páginas

O algoritmo calcula offset na página atual, bytes restantes nela e o menor valor entre esse restante e os bytes que faltam na operação.

Copia o chunk e repete.

Consequentemente cada página cruzada passa por tradução e flags próprias. Não existe a falha de validar apenas a primeira PTE de um buffer longo.

## Acesso físico pela visão do kernel

`mm_translate` devolve endereço físico. `user_copy` converte para endereço kernel com `bootinfo_phys_to_virt(phys)`.

O comentário da fonte explicita a estratégia: copiar pelo HHDM das páginas presentes; página ausente vira erro em vez de page fault em ring 0.

O objetivo é não transformar um ponteiro user inválido esperado em exceção privilegiada durante syscall.

## Relação com demand paging

O page-fault handler de processo pode materializar VM, stack, heap e framebuffer quando uma instrução user toca uma página lazy.

`user_copy` não chama `proc_fault_demand`. Existem, então, políticas distintas:
- user instruction pode faultar, ser reconhecida como acesso lazy válido e retry;
- kernel copy exige página presente e retorna erro se não estiver.

Isso mantém alocação fora da primitiva de cópia e evita depender de fault recovery dentro de ring 0.

Um programa deve garantir que seu buffer de syscall esteja materializado.

## Direções

`to_user = 0`: user → kernel.
`to_user = 1`: kernel → user.

`copy_from_user` e `copy_to_user` encapsulam as duas direções.

O kernel buffer é fornecido pelo caller e continua sendo responsabilidade da syscall. A primitiva não aloca nem tenta descobrir seu tamanho.

## Exemplo SYS_WRITE

`SYS_WRITE` só aceita fd 1 e no máximo 80 bytes. O buffer local tem 81 bytes.

O byte extra corrige um bug concreto: depois de copiar `n` bytes, `syscall_write_term` grava NUL em `buf[n]`. Com array de 80 bytes, `n == 80` seria overflow.

Fluxo:
1. validar fd/length;
2. copy-from-user;
3. inserir terminador com capacity check;
4. serial output;
5. retornar count.

O user pointer nunca é passado diretamente a `serial_puts`.

## Exemplo FREAD

`SYS_FREAD` valida ownership do fd e limita a 512 bytes. Filesystem escreve em kernel buffer. Só depois o kernel executa copy-to-user do número realmente lido.

Destino não mapeado, supervisor-only ou read-only vira retorno -1.

Assim filesystem não precisa conhecer page tables de usuário.

## Exemplo FWRITE

`SYS_FWRITE` copia primeiro até 512 bytes para kernel buffer. Depois trata stdout ou valida descriptor owner para arquivo.

Esse “copy then act” cria snapshot kernel estável para a operação. A camada inferior não percorre um buffer user mutável diretamente.

Não resolve todo possível TOCTOU de arquiteturas com shared memory, mas reduz a superfície para este desenho.

## Paths

`SYS_FOPEN` copia `UPATH_MAX - 1` bytes para array kernel de 128 bytes, força último byte a zero e então procura terminador.

`user_copy` continua byte-oriented; não interpreta string. Semântica C-string fica no caller depois da cópia.

## Canonicalidade

`0x0000800000000000` é a fronteira lower-half usada pelo modelo atual de 48-bit VA. A política rejeita qualquer span que atinja ou ultrapasse esse limite.

Hardware com LA57 pode oferecer outra canonicalidade, mas o ChrisOS revisado não deve ser documentado como se automaticamente usasse 57-bit paging.

## Flags de permissão

A camada consome `MM_PRESENT`, `MM_USER` e `MM_WRITE`.

Especialmente copy-to-user precisa respeitar `MM_WRITE`. Fazer ring 0 escrever em página user read-only violaria o contrato de proteção do processo mesmo que a CPU permitisse ao supervisor algum caminho privilegiado.

## Contenção de faults

Como cada chunk é autorizado antes do acesso físico, ponteiros inválidos usuais viram erro de syscall em vez de exception.

Isso não torna impossível um kernel fault: page tables corrompidas, HHDM incorreto ou bug de tradução ainda são falhas privilegiadas. A garantia é específica contra input user esperado como inválido.

## Janela entre tradução e cópia

Existe uma janela explícita entre provar a tradução e movimentar os bytes. A função traduz sob o lock da MM, retorna o endereço físico e somente depois acessa o frame via HHDM. Se outro CPU pudesse remover o mapping e devolver o mesmo frame à PMM nesse intervalo, uma tradução válida deixaria de ser garantia suficiente de lifetime.

No modelo atual, processos user e syscalls nativas ficam no BSP e o teardown do processo corrente não ocorre concorrentemente em outro core. Essa restrição é parte do argumento de segurança de memória, não apenas uma escolha de scheduler.

Para userspace SMP seria necessário acrescentar uma garantia de lifetime: referência ao address space/processo, pinning dos frames, read-side lock que cubra validação+cópia ou outro protocolo de reclamation. Apenas transformar `g_current` em per-CPU não resolveria essa corrida.

## Teardown e concorrência

`proc_destroy` libera páginas e address space. Atualmente syscall e process lifecycle user são BSP-only, então a cópia do processo atual não compete com teardown remoto em outro CPU.

Se teardown concorrente for permitido no futuro, a cópia precisará segurar referência/lock que impeça desalocação de page tables e frames enquanto traduz/copia.

Scheduler limitation e memory safety estão, portanto, ligados.

## Hardening não presente

A implementação cobre validação arquitetural de páginas, mas não afirma possuir toda a infraestrutura de kernels maduros: exception tables para copy faults, SMAP enable/disable, barreiras específicas contra speculation, hardened user accessors e pinning complexo não aparecem neste caminho.

Não é correto sugerir essas propriedades por inferência.

## Desempenho

Cada página é traduzida e cada chunk copiado byte a byte. Para limites atuais de 80/512 bytes, custo permanece pequeno e código é simples de auditar.

I/O maior pode justificar bulk copy, iovecs validados ou pinning. Qualquer otimização deve preservar autorização por página.

## Evidência executável existente

O repositório possui `tools/test_sys_write.c`, que valida uma fronteira concreta usada por `SYS_WRITE`: payload de 80 bytes exige capacidade 81 para o NUL final, capacidade 80 é rejeitada e comprimento 81 também é rejeitado. Essa evidência cobre `syscall_write_term`, que fica imediatamente depois de copy-from-user no caminho de console.

Ela não executa `user_copy`, não monta page tables sintéticas e não prova crossing de páginas, flags `USER/WRITE` ou lifetime entre tradução e cópia. Na inspeção atual não há um host test dedicado à função estática `user_copy`. Esses contratos ainda precisam de testes específicos, idealmente combinando casos host para o walker com gates em QEMU para o caminho real de syscall.

## Validação

Casos necessários incluem zero length, limites exatos, overflow, buffer em uma página, crossing válido, segunda página ausente, supervisor-only, read-only em copy-to-user, CR3 inválido, write de 80 bytes com terminador e I/O de 512 bytes.

## Matriz de decisão da cópia

| Situação | Resultado atual |
|---|---|
| `n == 0` | sucesso sem consultar CR3 |
| endereço inicial no upper half | erro |
| soma endereço+comprimento cruzaria limite canônico | erro |
| span sai da janela configurada | erro |
| CR3 atual é zero | erro |
| algum nível da tradução não está presente | erro |
| leaf sem `MM_USER` | erro |
| copy-to-user em leaf sem `MM_WRITE` | erro |
| várias páginas válidas | cópia por chunks, com nova tradução |
| página lazy ainda ausente | erro; a cópia não faz demand paging |

A tabela evidencia que "ponteiro dentro da faixa" é apenas a primeira condição. A autorização real combina range, address-space ownership, page walk e permissões.

## Limitações atuais

A política usa uma janela global low/high, não uma lookup completa de VMAs. Cópia é byte-oriented. Página ausente retorna erro. Não há SMAP-aware accessor, exception-table recovery nem refcount para teardown concorrente.

Mesmo assim os invariantes centrais estão implementados: faixa/canonicalidade, CR3 correto, validação por página, User bit e Write bit na direção apropriada.

## Reconciliação de revisão

O capítulo foi reconciliado com a revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Os commits intermediários não alteraram `syscall.c`, `mm.c`, `proc.c` nem o mecanismo HHDM descrito aqui; portanto o avanço de `reviewed_revision` não implica atribuir comportamento novo à implementação.

## Mapa de fonte

A fronteira fica em `kernel/metal/syscall.c`. CR3 vem de `proc.c`. Tradução/flags estão em `mm.c`/`mm.h`. Conversão phys→virt vem de `bootinfo.c`. O Source Atlas contém a íntegra desses arquivos na revisão `da3df29cb397932c43d32373871fb9380e688ade`.
