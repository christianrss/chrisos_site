(() => {
  const toggle = document.getElementById('nav-toggle');
  const panel = document.getElementById('nav-panel');
  if (toggle && panel) toggle.addEventListener('click', () => {
    const open = panel.classList.toggle('is-open');
    toggle.setAttribute('aria-expanded', String(open));
  });
  // Large source mirrors stay outside the search index; the Source Atlas remains complete.
  const input = document.getElementById('site-search');
  const output = document.getElementById('search-results');
  const base = document.body.dataset.base || '.';
  const root = new URL(base.replace(/\/$/, '') + '/', location.href);
  let pending, timer, sequence = 0;
  async function index() {
    if (!pending) pending = fetch(new URL('search/' + document.documentElement.lang + '.json', root))
      .then(r => { if (!r.ok) throw Error(r.status); return r.json(); })
      .then(x => (x.docs || []).filter(d => d.location.startsWith(document.documentElement.lang + '/')))
      .catch(e => { pending = null; throw e; });
    return pending;
  }
  if (input && output) input.addEventListener('input', () => {
    clearTimeout(timer);
    const current = ++sequence;
    output.replaceChildren();
    const terms = input.value.trim().toLocaleLowerCase().split(/\s+/);
    if (input.value.trim().length < 2) return;
    timer = setTimeout(async () => {
      try {
        const docs = await index();
        if (sequence !== current) return;
        const results = docs.map(d => {
          const title = (d.title || '').toLocaleLowerCase();
          const text = (title + ' ' + (d.text || '')).toLocaleLowerCase();
          if (!terms.every(t => text.includes(t))) return null;
          return { d, score: terms.reduce((n, t) => n + (title.includes(t) ? 5 : 1), 0) };
        }).filter(Boolean).sort((a, b) => b.score - a.score).slice(0, 12);
        output.replaceChildren(...results.map(({ d }) => {
          const a = document.createElement('a'); a.href = new URL(d.location, root); a.textContent = d.title || d.location; return a;
        }));
        if (!results.length) output.textContent = document.documentElement.lang === 'pt-br' ? 'Nenhum resultado.' : 'No results.';
      } catch {
        if (sequence === current) output.textContent = document.documentElement.lang === 'pt-br' ? 'Busca indisponível. Tente novamente.' : 'Search unavailable. Please retry.';
      }
    }, 180);
  });
  document.querySelectorAll('article table').forEach(table => {
    const box = document.createElement('div'); box.className = 'table-scroll'; box.tabIndex = 0;
    box.setAttribute('role', 'region'); box.setAttribute('aria-label', document.documentElement.lang === 'pt-br' ? 'Tabela com rolagem horizontal' : 'Horizontally scrollable table');
    table.before(box); box.append(table);
  });
  document.querySelectorAll('article img[src$=".svg"]').forEach(img => {
    if (img.closest('a')) return;
    const a = document.createElement('a'); a.href = img.src; a.target = '_blank'; a.rel = 'noopener';
    a.title = document.documentElement.lang === 'pt-br' ? 'Abrir diagrama em tamanho integral' : 'Open full-size diagram';
    img.before(a); a.append(img);
  });
})();
