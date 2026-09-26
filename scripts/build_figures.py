#!/usr/bin/env python3
"""Exact analytical figures, not runtime performance measurements."""
from pathlib import Path
from html import escape
OUT=Path('docs/assets/diagrams')

def svg(name,title,description,body,w=850,h=390):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title desc"><title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc><rect width="100%" height="100%" fill="#faf9f4"/><g font-family="Arial,sans-serif" fill="#111">{body}</g></svg>')

def main():
    body='<text x="30" y="35" font-size="20">Full-frame payload / conteúdo por segundo · 32 bpp · 60 Hz</text>'
    values=[]
    for i,(w,h) in enumerate([(640,480),(800,600),(1280,720),(1920,1080)]):
        mb=w*h*4*60/1e6;values.append(mb);y=80+i*58
        body+=f'<text x="25" y="{y+18}" font-size="15">{w} × {h}</text><rect x="160" y="{y}" width="{mb}" height="28" fill="#546e7a"/><text x="{170+mb}" y="{y+19}" font-size="14">{mb:.3f} MB/s</text>'
    body+='<text x="25" y="335" font-size="14">Model / modelo: width × height × 4 × 60 / 1,000,000</text><text x="25" y="360" font-size="13">Payload only; not measured traffic. / Apenas conteúdo; não é tráfego medido.</text>'
    svg('framebuffer-bandwidth.svg','Analytical framebuffer payload','Four computed full-frame payload rates, excluding read traffic and cache effects.',body)
    body='<text x="25" y="35" font-size="20">Sampling window / janela de amostragem</text><line x1="70" y1="150" x2="790" y2="150" stroke="#333"/>'
    body+='<rect x="330" y="70" width="210" height="190" fill="#e7d8ac" opacity="0.7"/><line x1="470" y1="60" x2="470" y2="280" stroke="#111" stroke-width="2"/>'
    body+='<text x="360" y="100">setup</text><text x="485" y="100">hold</text><text x="400" y="305">capture edge / borda</text><path d="M70 220 H290 V185 H750" fill="none" stroke="#31566b" stroke-width="3"/><text x="75" y="250">data stable / dado estável</text><text x="25" y="345">Setup: t_cq,max + t_pd,max + t_setup ≤ T + s</text><text x="25" y="370">Hold: t_cq,min + t_cd,min ≥ s + t_hold · schematic / esquemático</text>'
    svg('clock-window.svg','Setup and hold sampling window','A schematic data transition before setup, stable across the capture edge and hold interval. Not to scale.',body)
    body='<text x="25" y="35" font-size="20">Logic ranges / faixas lógicas · illustrative 1 V interface</text>'
    body+='<rect x="60" y="100" width="210" height="80" fill="#b9d2c3"/><rect x="270" y="100" width="280" height="80" fill="#e7d8ac"/><rect x="550" y="100" width="210" height="80" fill="#b9cbd7"/>'
    body+='<text x="115" y="145">0 / LOW</text><text x="295" y="145">undefined / indefinido</text><text x="600" y="145">1 / HIGH</text>'
    for x,label in [(60,'0 V'),(270,'0.3 V'),(550,'0.7 V'),(760,'1 V')]:
        body+=f'<line x1="{x}" y1="185" x2="{x}" y2="200" stroke="#111"/><text x="{x-15}" y="225">{label}</text>'
    body+='<text x="25" y="280">Input thresholds only; not a ChrisOS hardware specification.</text><text x="25" y="310">Limiares de entrada ilustrativos; não especificam o hardware do ChrisOS.</text>'
    svg('voltage-levels.svg','Illustrative input logic levels','An illustrative low range up to 0.3 V and high range from 0.7 V, with an undefined interval in between.',body)
    # Dimensionless abrupt-junction example: NA/ND=4, xp=1, xn=4.
    # Charge normalized by q*ND, field by q*ND*xp/epsilon,
    # potential by q*ND*xp^2/epsilon. No device measurement.
    body='<text x="25" y="32" font-size="20">Abrupt junction / junção abrupta · normalized model</text>'
    body+='<text x="25" y="57" font-size="13">N_A / N_D = 4 · x_p = 1 · x_n = 4 · dimensionless / adimensional</text>'
    profiles=[('rho / charge density / densidade de carga', -4, 1,
               [(-1,0),(-1,-4),(0,-4),(0,1),(4,1),(4,0)]),
              ('E / electric field / campo elétrico', -4, 0,
               [(-1,0),(0,-4),(4,0)]),
              ('phi / potential / potencial', 0, 10,
               [(i/20, 2*(i/20+1)**2 if i<=0 else 2+4*(i/20)-(i/20)**2/2)
                for i in range(-20,81)])]
    for row,(title,lo,hi,points) in enumerate(profiles):
        top=95+row*190
        X=lambda x:140+(x+1)*120
        Y=lambda y:top+110-(y-lo)/(hi-lo)*100
        body+=f'<text x="25" y="{top-10}" font-size="15">{escape(title)}</text>'
        body+=f'<line x1="140" y1="{Y(0)}" x2="740" y2="{Y(0)}" stroke="#777"/>'
        body+=f'<line x1="260" y1="{top}" x2="260" y2="{top+120}" stroke="#999" stroke-dasharray="4 4"/>'
        coords=' '.join(f'{X(x):.2f},{Y(y):.2f}' for x,y in points)
        body+=f'<polyline points="{coords}" fill="none" stroke="#31566b" stroke-width="3"/>'
        for x,label in [(-1,'-1'),(0,'0'),(4,'4')]:
            body+=f'<text x="{X(x)-8}" y="{top+140}" font-size="13">{label}</text>'
        body+=f'<text x="95" y="{Y(lo)+4}" font-size="13">{lo}</text><text x="95" y="{Y(hi)+4}" font-size="13">{hi}</text>'
    body+='<text x="25" y="680" font-size="13">x: normalized position / posição normalizada · p: -1 to 0 · n: 0 to 4</text>'
    body+='<text x="25" y="708" font-size="13">dE/dx = rho; dphi/dx = -E in these units. Not measured / não medido.</text>'
    svg('junction-profiles.svg','Normalized charge, field and potential',
        'Abrupt-junction model with acceptor density four times donor density. Charge is -4 on the p side and +1 on the n side. Field is continuous and negative; potential rises continuously from 0 to 10.',body,h=735)
    print('analytical figures: 4')
if __name__=='__main__':main()
