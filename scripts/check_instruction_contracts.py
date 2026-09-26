#!/usr/bin/env python3
"""Compile the actual decoder/operand helpers and test independent literal cases.

Rejecting memory stubs deliberately exclude guest execution from this probe.
"""
import argparse
import ctypes
import hashlib
from pathlib import Path
import subprocess
import tempfile

FIELDS = 'len os asz rex mod reg rm digit has_modrm has_sib scale index base no_base no_index rip_rel disp has_disp imm imm_bytes cc alu'.split()
CASES = [
    ('b82a000000', 'MOV', dict(os=4, rm=0, imm=42, imm_bytes=4)),
    ('83c001', 'ALU', dict(os=4, mod=3, rm=0, digit=0, imm=1)),
    ('c3', 'RET', {}),
    ('4801d8', 'ALU', dict(os=8, mod=3, reg=3, rm=0)),
    ('6601d8', 'ALU', dict(os=2, mod=3, reg=3, rm=0)),
    ('ebfe', 'JMP', dict(imm=254, imm_bytes=1)),
    ('e8fb000000', 'CALL', dict(imm=251, imm_bytes=4)),
    ('75fc', 'Jcc', dict(cc=5, imm=252, imm_bytes=1)),
    ('0f85fcffffff', 'Jcc', dict(cc=5, imm=0xfffffffc, imm_bytes=4)),
    ('488b448df0', 'MOV', dict(os=8, mod=1, reg=0, rm=4, has_sib=1, scale=2, index=1, base=5, disp=-16)),
    ('488b0578563412', 'MOV', dict(os=8, rip_rel=1, disp=0x12345678)),
    ('678b00', 'MOV', dict(os=4, asz=4, mod=0, rm=0)),
    ('4d89c8', 'MOV', dict(os=8, reg=9, rm=8, mod=3)),
    ('4150', 'PUSH', dict(os=8, rm=8)),
    ('88e0', 'MOV', dict(os=1, rex=0, reg=4, rm=0)),
    ('4088e0', 'MOV', dict(os=1, rex=0x40, reg=4, rm=0)),
    ('488b042500200000', 'MOV', dict(has_sib=1, no_base=1, no_index=1, disp=0x2000)),
    ('488b4500', 'MOV', dict(mod=1, rm=5, disp=0, has_disp=1)),
    ('90', 'NOP', {}),
    ('f4', 'HLT', {}),
]

WRAPPER = r'''
#include "machine/machine.h"
#include <string.h>
int chris_va_read(ChrisCpu *c,uint64_t a,void *d,size_t n,int k){
    (void)c;(void)a;(void)d;(void)n;(void)k;return -1;
}
int chris_va_write(ChrisCpu *c,uint64_t a,const void *s,size_t n){
    (void)c;(void)a;(void)s;(void)n;return -1;
}
int doc_decode(const uint8_t *b,int n,int64_t *fields,char *name){
    ChrisInsn in; int rc=chris_decode(b,n,&in); if(rc<0)return rc;
    FIELD_ASSIGNMENTS
    strncpy(name,chris_op_name(in.op),15); name[15]=0; return rc;
}
int doc_is_add(int64_t n){return n==CHRIS_ALU_ADD;}
int doc_reg(int reg,int os,int rex,uint64_t *stored,uint64_t *read){
    ChrisCpu c; ChrisInsn in; memset(&c,0,sizeof c);memset(&in,0,sizeof in);
    for(int i=0;i<16;i++)c.arch.gpr[i]=0x1122334455667788ull;
    in.os=os;in.rex=rex;
    int rc=chris_write_gpr(&c,&in,reg,os,0xaabbccddull);if(rc)return rc;
    int idx=os==1&&!rex&&reg>=4&&reg<=7?reg-4:reg;
    *stored=c.arch.gpr[idx];return chris_read_gpr(&c,&in,reg,os,read);
}
int doc_address(const uint8_t *b,int n,uint64_t *addr){
    ChrisCpu c; ChrisInsn in;memset(&c,0,sizeof c);
    for(int i=0;i<16;i++)c.arch.gpr[i]=(uint64_t)(i+1)*0x1000;
    c.arch.rip=0x100000;if(chris_decode(b,n,&in)<0)return -1;
    return chris_eff_addr(&c,&in,addr);
}
'''

def require(condition, message):
    if not condition:
        raise SystemExit('FAIL: ' + message)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='.source')
    parser.add_argument('--cc', default='cc')
    args=parser.parse_args()
    root=Path(args.source).resolve()/ 'chrisvm'
    paths=[root/'cpu/common/state.c',root/'cpu/emulator/decode.c',root/'cpu/emulator/operands.c']
    with tempfile.TemporaryDirectory(prefix='chris-instruction-') as tmp:
        wrapper=Path(tmp)/'probe.c'; library=Path(tmp)/'probe.so'
        assignments='\n'.join(f'fields[{i}]=(int64_t)in.{name};' for i,name in enumerate(FIELDS))
        wrapper.write_text(WRAPPER.replace('FIELD_ASSIGNMENTS',assignments))
        subprocess.run([args.cc,'-std=c11','-Wall','-Wextra','-Werror','-O2','-shared','-fPIC',f'-I{root}',str(wrapper),*map(str,paths),'-o',str(library)],check=True)
        lib=ctypes.CDLL(str(library))
        p64=ctypes.POINTER(ctypes.c_uint64)
        lib.doc_decode.argtypes=[ctypes.c_char_p,ctypes.c_int,ctypes.POINTER(ctypes.c_int64),ctypes.c_char_p]
        lib.doc_is_add.argtypes=[ctypes.c_int64]
        lib.doc_reg.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_int,p64,p64]
        lib.doc_address.argtypes=[ctypes.c_char_p,ctypes.c_int,p64]
        fields=(ctypes.c_int64*len(FIELDS))(); name=ctypes.create_string_buffer(16)
        truncations=0
        for encoded,operation,expected in CASES:
            raw=bytes.fromhex(encoded)
            rc=lib.doc_decode(raw,len(raw),fields,name)
            require(rc==len(raw),f'{encoded}: consumed {rc}')
            require(name.value.decode()==operation,f'{encoded}: operation {name.value!r}')
            actual=dict(zip(FIELDS,fields))
            for key,value in dict(len=len(raw),**expected).items():
                require(actual[key]==value,f'{encoded}: {key}={actual[key]}, expected {value}')
            if operation=='ALU':
                require(lib.doc_is_add(actual['alu'])==1,f'{encoded}: ADD identity')
            for length in range(len(raw)):
                require(lib.doc_decode(raw,length,fields,name)<0,f'{encoded}: accepted truncation {length}')
                truncations+=1
        require(lib.doc_decode(bytes.fromhex('0f0b'),2,fields,name)==2 and name.value==b'UD','UD classification')
        stored=ctypes.c_uint64(); read=ctypes.c_uint64(); registers=0
        for reg in range(16):
            for size,expected in [(2,0x112233445566ccdd),(4,0xaabbccdd),(8,0xaabbccdd)]:
                require(lib.doc_reg(reg,size,0,ctypes.byref(stored),ctypes.byref(read))==0,'register status')
                require(stored.value==expected,f'register {reg}/{size}: preservation')
                require(read.value==(0xaabbccdd & ((1<<(size*8))-1)),f'register {reg}/{size}: read')
                registers+=1
            for rex in (0,0x40):
                expected=0x112233445566dd88 if rex==0 and 4<=reg<=7 else 0x11223344556677dd
                require(lib.doc_reg(reg,1,rex,ctypes.byref(stored),ctypes.byref(read))==0,'byte status')
                require(stored.value==expected and read.value==0xdd,f'byte {reg}/{rex}: alias')
                registers+=1
        for reg in (-1,16):
            require(lib.doc_reg(reg,8,0,ctypes.byref(stored),ctypes.byref(read))<0,'invalid register accepted')
        addresses=[('488b448df0',0xdff0),('488b0578563412',0x100007+0x12345678),('488b042500200000',0x2000),('488b4500',0x6000)]
        for encoded,expected in addresses:
            raw=bytes.fromhex(encoded)
            require(lib.doc_address(raw,len(raw),ctypes.byref(stored))==0 and stored.value==expected,f'{encoded}: effective address')
        print(f'PASS: {len(CASES)} instruction fixtures; {truncations} truncations; {registers} register cases; 2 invalid registers; {len(addresses)} addresses; 1 UD classification')
        for path in paths:
            print(hashlib.sha256(path.read_bytes()).hexdigest(),path.relative_to(root.parent))

if __name__=='__main__':
    main()
