/* Independent fixtures for the real ChrisCPU walker; no guest exception delivery. */
#include "machine/machine.h"
#include <stdio.h>
#include <string.h>

static unsigned char memory[65536];
static int reads, writes, reject_pte_writes, checks, gaps;
static int vector_seen;
static uint32_t error_seen;

int chris_phys_read(ChrisMachine *m, uint64_t pa, void *dst, size_t n) {
    (void)m;
    reads++;
    if (pa > sizeof memory || n > sizeof memory - pa) return -1;
    memcpy(dst, memory + pa, n);
    return 0;
}
int chris_phys_write(ChrisMachine *m, uint64_t pa, const void *src, size_t n) {
    (void)m;
    writes++;
    if (reject_pte_writes && pa < 0x5000) return -1;
    if (pa > sizeof memory || n > sizeof memory - pa) return -1;
    memcpy(memory + pa, src, n);
    return 0;
}
int chris_raise(ChrisCpu *cpu, int vector, int has_error, uint32_t error) {
    (void)cpu;(void)has_error;
    vector_seen=vector;error_seen=error;
    return -1;
}
static void pte(uint64_t address, uint64_t value) {memcpy(memory+address,&value,8);}
static uint64_t entry(uint64_t address) {uint64_t v;memcpy(&v,memory+address,8);return v;}
static void setup(ChrisCpu *c) {
    memset(c,0,sizeof *c);memset(memory,0,sizeof memory);
    c->arch.cr0=CHRIS_CR0_PG|CHRIS_CR0_WP;c->arch.cr3=0x1000;
    pte(0x1000,0x2007);pte(0x2000,0x3007);pte(0x3000,0x4007);
    pte(0x4008,0x8007);
    reads=0;writes=0;reject_pte_writes=0;vector_seen=-1;error_seen=0;
}
#define CHECK(condition, label) do {checks++;if(!(condition)){fprintf(stderr,"FAIL: %s\n",label);return 1;}} while(0)
#define GAP(condition, label) do {gaps++;if(!(condition)){fprintf(stderr,"REVIEW changed documented gap: %s\n",label);return 1;}printf("KNOWN GAP: %s\n",label);} while(0)
int main(void) {
    ChrisCpu c;uint64_t pa=0;uint32_t err=0;unsigned char out[4]={0};
    setup(&c);c.arch.cr0=0;
    CHECK(chris_translate(&c,0x1234,&pa,0,&err)==0&&pa==0x1234&&reads==0,"paging disabled");
    setup(&c);
    CHECK(chris_translate(&c,0x1234,&pa,0,&err)==0&&pa==0x8234,"four-level address");
    CHECK(reads==4&&writes==4,"cold walk accesses four entries");
    CHECK((entry(0x1000)&32)&&(entry(0x2000)&32)&&(entry(0x3000)&32)&&(entry(0x4008)&32),"accessed bits");
    CHECK(!(entry(0x4008)&64),"read leaves dirty clear");
    CHECK(chris_translate(&c,0x1234,&pa,1,&err)==0&&(entry(0x4008)&64),"write sets dirty");
    setup(&c);
    CHECK(chris_translate(&c,0x0000800000000000ull,&pa,0,&err)==-2&&reads==0,"noncanonical address");
    setup(&c);pte(0x4008,0);c.arch.cpl=3;
    CHECK(chris_translate(&c,0x1234,&pa,1,&err)==-1&&err==6,"user missing write code");
    setup(&c);pte(0x1000,0x2003);c.arch.cpl=3;
    CHECK(chris_translate(&c,0x1234,&pa,0,&err)==-1&&err==5,"ancestor user denial");
    setup(&c);pte(0x1000,0x2005);
    CHECK(chris_translate(&c,0x1234,&pa,1,&err)==-1&&err==3,"supervisor WP denial");
    c.arch.cr0&=~CHRIS_CR0_WP;
    CHECK(chris_translate(&c,0x1234,&pa,1,&err)==0,"supervisor WP disabled");
    c.arch.cpl=3;
    CHECK(chris_translate(&c,0x1234,&pa,1,&err)==-1&&err==7,"user write remains denied");
    setup(&c);pte(0x4008,0x8000000000008007ull);c.arch.efer=CHRIS_EFER_NXE;c.arch.cpl=3;
    CHECK(chris_translate(&c,0x1234,&pa,2,&err)==-1&&err==21,"NX execution denial");
    GAP(chris_translate(&c,0x1234,&pa,0,&err)==0&&pa==0x8000000000008234ull,"4 KiB leaf leaks NX into data physical address");
    setup(&c);pte(0x3000,0x200087);
    CHECK(chris_translate(&c,0x1234,&pa,0,&err)==0&&pa==0x201234&&reads==3,"2 MiB leaf");
    setup(&c);pte(0x2000,0x40000087);
    CHECK(chris_translate(&c,0x1234,&pa,0,&err)==0&&pa==0x40001234&&reads==2,"1 GiB leaf");
    setup(&c);reject_pte_writes=1;
    GAP(chris_translate(&c,0x1234,&pa,0,&err)==0&&writes==4&&!(entry(0x4008)&32),"accessed-bit write failure ignored");
    setup(&c);c.arch.cr3=0x10000;
    CHECK(chris_translate(&c,0x1234,&pa,0,&err)==-3,"unbacked table distinct from page fault");
    setup(&c);pte(0x4008,0);
    CHECK(chris_va_read(&c,0x1234,out,1,0)==-1&&vector_seen==CHRIS_EX_PF&&c.arch.cr2==0x1234&&error_seen==0,"read wrapper page-fault report");
    setup(&c);
    CHECK(chris_va_read(&c,0x0000800000000000ull,out,1,0)==-1&&vector_seen==CHRIS_EX_GP,"read wrapper general protection");
    setup(&c);c.arch.cr3=0x10000;
    CHECK(chris_va_read(&c,0x1234,out,1,0)==-1&&c.exit_reason==CHRIS_EXIT_UNMAPPED&&c.halted,"read wrapper monitor exit");
    setup(&c);pte(0x4008,0);c.delivering=1;
    CHECK(chris_va_read(&c,0x1234,out,1,0)==-1&&vector_seen==-1,"delivery suppresses recursive raise");
    setup(&c);memory[0x8ffe]=0xaa;memory[0x8fff]=0xbb;
    CHECK(chris_va_read(&c,0x1ffe,out,4,0)==-1&&out[0]==0xaa&&out[1]==0xbb&&c.arch.cr2==0x2000,"read crossing missing second page");
    setup(&c);const unsigned char input[4]={1,2,3,4};
    GAP(chris_va_write(&c,0x1ffe,input,4)==-1&&memory[0x8ffe]==1&&memory[0x8fff]==2&&c.arch.cr2==0x2000,"cross-page write retains first chunk after second-page fault");
    setup(&c);
    CHECK(chris_va_read(&c,0,out,0,0)==0&&chris_va_write(&c,0,input,0)==0&&reads==0&&writes==0,"zero-length accesses");
    printf("PASS: %d MMU contract checks; %d known-gap characterizations (not architectural conformance)\n",checks,gaps);
    return 0;
}
