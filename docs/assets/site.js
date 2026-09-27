(() => {
  const lang = document.documentElement.lang === 'pt-br' ? 'pt-br' : 'en';
  const pt = lang === 'pt-br';
  const body = document.body;
  const base = body.dataset.base || '.';
  const configuredRoot = body.dataset.siteRoot || '';
  const root = configuredRoot
    ? new URL(configuredRoot.endsWith('/') ? configuredRoot : configuredRoot + '/')
    : new URL(base.replace(/\/$/, '') + '/', location.href);

  /* ---------- Book drawer ---------- */
  const navToggle = document.getElementById('nav-toggle');
  const navClose = document.getElementById('nav-close');
  const navPanel = document.getElementById('nav-panel');
  const navBackdrop = document.getElementById('nav-backdrop');
  const mobileMenu = document.querySelector('.mobile-book-menu');

  function openNav() {
    if (!navPanel) return;
    navPanel.classList.add('is-open');
    body.classList.add('nav-open');
    navToggle?.setAttribute('aria-expanded', 'true');
    if (navBackdrop) navBackdrop.hidden = false;
    navClose?.focus({ preventScroll: true });
  }

  function closeNav({ restoreFocus = false } = {}) {
    if (!navPanel) return;
    navPanel.classList.remove('is-open');
    body.classList.remove('nav-open');
    navToggle?.setAttribute('aria-expanded', 'false');
    if (navBackdrop) navBackdrop.hidden = true;
    if (restoreFocus) navToggle?.focus({ preventScroll: true });
  }

  navToggle?.addEventListener('click', () => {
    navPanel?.classList.contains('is-open') ? closeNav() : openNav();
  });
  navClose?.addEventListener('click', () => closeNav({ restoreFocus: true }));
  navBackdrop?.addEventListener('click', () => closeNav());
  mobileMenu?.addEventListener('click', openNav);

  navPanel?.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => {
      if (matchMedia('(max-width: 820px)').matches) closeNav();
    });
  });

  /* Section titles are real links; clicking the title navigates, while clicking
     the remaining summary row expands or collapses the hierarchy. */
  navPanel?.querySelectorAll('.section-title-link').forEach(link => {
    link.addEventListener('click', event => event.stopPropagation());
  });

  const activeBookLink = navPanel?.querySelector('a.active');
  if (activeBookLink) {
    let node = activeBookLink.parentElement;
    while (node && node !== navPanel) {
      if (node.tagName === 'DETAILS') node.open = true;
      node = node.parentElement;
    }
    requestAnimationFrame(() => {
      activeBookLink.scrollIntoView({ block: 'center', inline: 'nearest' });
    });
  }

  /* ---------- Sidebar filtering ---------- */
  const sidebarFilter = document.getElementById('sidebar-filter');
  const sidebarFilterClear = document.getElementById('sidebar-filter-clear');
  const sidebarFilterStatus = document.getElementById('sidebar-filter-status');

  function filterSidebar() {
    if (!navPanel || !sidebarFilter) return;
    const term = normalize(sidebarFilter.value.trim());
    const pages = [...navPanel.querySelectorAll('.book-page')];
    const sections = [...navPanel.querySelectorAll('.section')];

    if (!term) {
      pages.forEach(item => item.hidden = false);
      sections.forEach(item => item.hidden = false);
      if (sidebarFilterStatus) sidebarFilterStatus.textContent = '';
      return;
    }

    let visiblePages = 0;
    pages.forEach(item => {
      const match = normalize(item.textContent).includes(term);
      item.hidden = !match;
      if (match) visiblePages += 1;
    });

    [...sections].reverse().forEach(section => {
      const ownTitle = normalize(section.querySelector(':scope > details > summary .section-title-link')?.textContent);
      const childMatch = [...section.querySelectorAll('.book-page, .section')]
        .some(child => child !== section && !child.hidden);
      const match = ownTitle.includes(term) || childMatch;
      section.hidden = !match;
      const details = section.querySelector(':scope > details');
      if (details && match) details.open = true;
    });

    if (sidebarFilterStatus) {
      sidebarFilterStatus.textContent = pt
        ? visiblePages + (visiblePages === 1 ? ' capítulo encontrado' : ' capítulos encontrados')
        : visiblePages + (visiblePages === 1 ? ' chapter found' : ' chapters found');
    }
  }

  sidebarFilter?.addEventListener('input', filterSidebar);
  sidebarFilterClear?.addEventListener('click', () => {
    if (!sidebarFilter) return;
    sidebarFilter.value = '';
    filterSidebar();
    sidebarFilter.focus();
  });

  /* ---------- Search ---------- */
  const searchToggle = document.getElementById('search-toggle');
  const searchDialog = document.getElementById('search-dialog');
  const searchClose = document.getElementById('search-close');
  const searchInput = document.getElementById('global-search');
  const searchOutput = document.getElementById('global-search-results');
  const openSearchButtons = document.querySelectorAll('.open-global-search');

  let searchPromise = null;
  let searchTimer = null;
  let searchSequence = 0;
  let selectedResult = -1;

  function normalize(text) {
    return String(text || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLocaleLowerCase();
  }

  async function loadIndex() {
    if (!searchPromise) {
      searchPromise = (async () => {
        const candidates = [
          new URL('search/' + lang + '.json', root),
          new URL('search/search_index.json', root)
        ];
        let lastError = null;

        for (const url of candidates) {
          try {
            const response = await fetch(url, { credentials: 'same-origin' });
            if (!response.ok) throw new Error('search index ' + response.status);
            const data = await response.json();
            const docs = (data.docs || [])
              .filter(doc => String(doc.location || '').startsWith(lang + '/'))
              .map(doc => ({
                ...doc,
                _title: normalize(doc.title),
                _location: normalize(doc.location),
                _text: normalize(doc.text)
              }));
            if (docs.length) return docs;
          } catch (error) {
            lastError = error;
          }
        }

        throw lastError || new Error('search index unavailable');
      })().catch(error => {
        searchPromise = null;
        throw error;
      });
    }
    return searchPromise;
  }

  function openSearch() {
    if (!searchDialog) return;
    closeNav();
    searchDialog.hidden = false;
    body.classList.add('search-open');
    searchToggle?.setAttribute('aria-expanded', 'true');
    selectedResult = -1;
    requestAnimationFrame(() => searchInput?.focus());
  }

  function closeSearch({ restoreFocus = false } = {}) {
    if (!searchDialog) return;
    searchDialog.hidden = true;
    body.classList.remove('search-open');
    searchToggle?.setAttribute('aria-expanded', 'false');
    if (restoreFocus) searchToggle?.focus({ preventScroll: true });
  }

  searchToggle?.addEventListener('click', openSearch);
  searchClose?.addEventListener('click', () => closeSearch({ restoreFocus: true }));
  openSearchButtons.forEach(button => button.addEventListener('click', openSearch));
  searchDialog?.addEventListener('click', event => {
    if (event.target === searchDialog) closeSearch();
  });

  function snippetFor(doc, terms) {
    const raw = String(doc.text || '').replace(/\s+/g, ' ').trim();
    if (!raw) return '';
    const low = normalize(raw);
    let index = Infinity;
    for (const term of terms) {
      const found = low.indexOf(term);
      if (found >= 0) index = Math.min(index, found);
    }
    if (!Number.isFinite(index)) index = 0;
    const start = Math.max(0, index - 72);
    const end = Math.min(raw.length, start + 210);
    return (start ? '…' : '') + raw.slice(start, end).trim() + (end < raw.length ? '…' : '');
  }

  function resultScore(doc, terms) {
    const title = doc._title ?? normalize(doc.title);
    const location = doc._location ?? normalize(doc.location);
    const text = doc._text ?? normalize(doc.text);
    let score = 0;
    for (const term of terms) {
      if (!text.includes(term) && !title.includes(term) && !location.includes(term)) return null;
      if (title === term) score += 40;
      else if (title.startsWith(term)) score += 22;
      else if (title.includes(term)) score += 14;
      if (location.includes(term)) score += 5;
      const occurrences = text.split(term).length - 1;
      score += Math.min(occurrences, 6);
    }
    if (doc.location === lang + '/') score -= 2;
    return score;
  }

  function setSelected(index) {
    const links = [...(searchOutput?.querySelectorAll('.search-result') || [])];
    if (!links.length) {
      selectedResult = -1;
      return;
    }
    selectedResult = Math.max(0, Math.min(index, links.length - 1));
    links.forEach((link, i) => link.classList.toggle('is-selected', i === selectedResult));
    links[selectedResult]?.scrollIntoView({ block: 'nearest' });
  }

  function renderResults(results, terms) {
    if (!searchOutput) return;
    searchOutput.replaceChildren();
    selectedResult = -1;

    if (!results.length) {
      const empty = document.createElement('div');
      empty.className = 'search-empty';
      empty.textContent = pt ? 'Nenhum resultado.' : 'No results.';
      searchOutput.append(empty);
      return;
    }

    const fragment = document.createDocumentFragment();
    for (const { doc } of results) {
      const link = document.createElement('a');
      link.className = 'search-result';
      link.setAttribute('role', 'option');
      link.href = new URL(doc.location, root);

      const title = document.createElement('span');
      title.className = 'search-result-title';
      title.textContent = doc.title || doc.location;

      const path = document.createElement('span');
      path.className = 'search-result-path';
      path.textContent = doc.location;

      const snippet = document.createElement('span');
      snippet.className = 'search-result-snippet';
      snippet.textContent = snippetFor(doc, terms);

      link.append(title, path, snippet);
      fragment.append(link);
    }
    searchOutput.append(fragment);
  }

  searchInput?.addEventListener('input', () => {
    clearTimeout(searchTimer);
    const current = ++searchSequence;
    const query = searchInput.value.trim();
    searchOutput?.replaceChildren();

    if (query.length < 2) {
      if (searchOutput) {
        const help = document.createElement('div');
        help.className = 'search-empty';
        help.textContent = pt ? 'Digite pelo menos dois caracteres.' : 'Type at least two characters.';
        searchOutput.append(help);
      }
      return;
    }

    const terms = normalize(query).split(/\s+/).filter(Boolean);
    searchTimer = setTimeout(async () => {
      try {
        const docs = await loadIndex();
        if (current !== searchSequence) return;
        const results = docs
          .map(doc => ({ doc, score: resultScore(doc, terms) }))
          .filter(item => item.score !== null)
          .sort((a, b) => b.score - a.score || String(a.doc.title).localeCompare(String(b.doc.title)))
          .slice(0, 24);
        renderResults(results, terms);
      } catch {
        if (current !== searchSequence || !searchOutput) return;
        searchOutput.replaceChildren();
        const error = document.createElement('div');
        error.className = 'search-empty';
        error.textContent = pt ? 'Busca indisponível. Recarregue a página e tente novamente.' : 'Search unavailable. Reload the page and retry.';
        searchOutput.append(error);
      }
    }, 110);
  });

  searchInput?.addEventListener('keydown', event => {
    const links = [...(searchOutput?.querySelectorAll('.search-result') || [])];
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setSelected(selectedResult + 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setSelected(selectedResult <= 0 ? links.length - 1 : selectedResult - 1);
    } else if (event.key === 'Enter' && selectedResult >= 0 && links[selectedResult]) {
      event.preventDefault();
      links[selectedResult].click();
    }
  });

  document.addEventListener('keydown', event => {
    const target = event.target;
    const typing = target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement ||
      target instanceof HTMLSelectElement ||
      target?.isContentEditable;

    if (event.key === '/' && !typing && searchDialog?.hidden) {
      event.preventDefault();
      openSearch();
    }

    if (event.key === 'Escape') {
      if (searchDialog && !searchDialog.hidden) closeSearch({ restoreFocus: true });
      else if (navPanel?.classList.contains('is-open')) closeNav({ restoreFocus: true });
    }
  });

  /* ---------- In-page contents ---------- */
  const tocLinks = [
    ...document.querySelectorAll('.chapter-rail a[href^="#"], .mobile-page-toc a[href^="#"]')
  ];

  const targets = new Map();
  for (const link of tocLinks) {
    const hash = link.getAttribute('href');
    if (!hash || hash === '#') continue;
    const id = decodeURIComponent(hash.slice(1));
    const target = document.getElementById(id);
    if (target) {
      if (!targets.has(target)) targets.set(target, []);
      targets.get(target).push(link);
    }
  }

  if ('IntersectionObserver' in window && targets.size) {
    const visible = new Map();
    const updateActive = () => {
      const entries = [...visible.entries()]
        .filter(([, value]) => value)
        .map(([element]) => element)
        .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);

      const current = entries[0] || [...targets.keys()]
        .filter(el => el.getBoundingClientRect().top <= 100)
        .pop();

      tocLinks.forEach(link => link.classList.remove('active-section'));
      if (current) (targets.get(current) || []).forEach(link => link.classList.add('active-section'));
    };

    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) visible.set(entry.target, entry.isIntersecting);
      updateActive();
    }, { rootMargin: '-12% 0px -74% 0px', threshold: [0, 1] });

    targets.forEach((_, element) => observer.observe(element));
  }

  document.querySelectorAll('.mobile-page-toc a[href^="#"]').forEach(link => {
    link.addEventListener('click', () => {
      const details = link.closest('details');
      if (details) details.open = false;
    });
  });

  /* ---------- Reading position ---------- */
  const scrollProgressBar = document.getElementById('reader-scroll-progress-bar');
  let scrollProgressFrame = 0;

  function updateScrollProgress() {
    scrollProgressFrame = 0;
    if (!scrollProgressBar) return;
    const article = document.querySelector('article');
    if (!article) {
      scrollProgressBar.style.width = '0%';
      return;
    }
    const start = article.offsetTop;
    const end = start + article.offsetHeight - window.innerHeight;
    const value = end <= start ? 1 : Math.min(1, Math.max(0, (window.scrollY - start) / (end - start)));
    scrollProgressBar.style.width = (value * 100).toFixed(2) + '%';
  }

  function scheduleScrollProgress() {
    if (scrollProgressFrame) return;
    scrollProgressFrame = requestAnimationFrame(updateScrollProgress);
  }

  window.addEventListener('scroll', scheduleScrollProgress, { passive: true });
  window.addEventListener('resize', scheduleScrollProgress, { passive: true });
  updateScrollProgress();

  /* ---------- Tables and diagrams ---------- */
  document.querySelectorAll('article table').forEach(table => {
    if (table.parentElement?.classList.contains('table-scroll')) return;
    const box = document.createElement('div');
    box.className = 'table-scroll';
    box.tabIndex = 0;
    box.setAttribute('role', 'region');
    box.setAttribute('aria-label', pt ? 'Tabela com rolagem horizontal' : 'Horizontally scrollable table');
    table.before(box);
    box.append(table);
  });

  document.querySelectorAll('article img[src$=".svg"]').forEach(img => {
    if (img.closest('a')) return;
    const link = document.createElement('a');
    link.href = img.src;
    link.target = '_blank';
    link.rel = 'noopener';
    link.title = pt ? 'Abrir diagrama em tamanho integral' : 'Open full-size diagram';
    img.before(link);
    link.append(img);
  });
})();
