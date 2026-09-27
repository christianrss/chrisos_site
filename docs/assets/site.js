(() => {
  const body = document.body;
  const lang = document.documentElement.lang === 'pt-br' ? 'pt-br' : 'en';
  const pt = lang === 'pt-br';
  const base = (body.dataset.base || '.').replace(/\/+$/, '');
  const root = new URL((base || '.') + '/', location.href);

  const navPanel = document.getElementById('nav-panel');
  const navToggle = document.getElementById('nav-toggle');
  const navClose = document.getElementById('nav-close');
  const navBackdrop = document.getElementById('nav-backdrop');
  const mobileMenu = document.querySelector('.mobile-book-menu');
  const activeBookLink = navPanel ? navPanel.querySelector('.book-page > a.active') : null;

  function openActiveAncestors() {
    if (!activeBookLink) return;
    let node = activeBookLink.parentElement;
    while (node && node !== navPanel) {
      if (node.classList && node.classList.contains('section-children')) {
        node.hidden = false;
        const section = node.parentElement;
        section && section.classList.add('is-open');
        const toggle = section && section.querySelector(':scope > .section-row > .section-toggle');
        toggle && toggle.setAttribute('aria-expanded', 'true');
      }
      node = node.parentElement;
    }
  }

  function centerActiveLink() {
    if (!navPanel || !activeBookLink) return;
    const panelRect = navPanel.getBoundingClientRect();
    const linkRect = activeBookLink.getBoundingClientRect();
    navPanel.scrollTop += linkRect.top - panelRect.top - navPanel.clientHeight * 0.42;
  }

  function openNav() {
    if (!navPanel) return;
    openActiveAncestors();
    navPanel.classList.add('is-open');
    body.classList.add('nav-open');
    navToggle && navToggle.setAttribute('aria-expanded', 'true');
    if (navBackdrop) navBackdrop.hidden = false;
    requestAnimationFrame(() => {
      centerActiveLink();
      navClose && navClose.focus({preventScroll:true});
    });
  }

  function closeNav(restoreFocus) {
    if (!navPanel) return;
    navPanel.classList.remove('is-open');
    body.classList.remove('nav-open');
    navToggle && navToggle.setAttribute('aria-expanded', 'false');
    if (navBackdrop) navBackdrop.hidden = true;
    if (restoreFocus && navToggle) navToggle.focus({preventScroll:true});
  }

  navToggle && navToggle.addEventListener('click', () => navPanel.classList.contains('is-open') ? closeNav(false) : openNav());
  navClose && navClose.addEventListener('click', () => closeNav(true));
  navBackdrop && navBackdrop.addEventListener('click', () => closeNav(false));
  mobileMenu && mobileMenu.addEventListener('click', openNav);

  document.querySelectorAll('.section-toggle').forEach(button => {
    button.addEventListener('click', () => {
      const section = button.closest('.book-section');
      const children = section && section.querySelector(':scope > .section-children');
      if (!children) return;
      const opening = children.hidden;
      children.hidden = !opening;
      section.classList.toggle('is-open', opening);
      button.setAttribute('aria-expanded', opening ? 'true' : 'false');
    });
  });

  navPanel && navPanel.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      if (matchMedia('(max-width:1120px)').matches) closeNav(false);
    });
  });

  openActiveAncestors();
  if (activeBookLink && !matchMedia('(max-width:1120px)').matches) {
    requestAnimationFrame(centerActiveLink);
  }

  const searchDialog = document.getElementById('search-dialog');
  const searchToggle = document.getElementById('search-toggle');
  const searchClose = document.getElementById('search-close');
  const searchInput = document.getElementById('global-search');
  const searchStatus = document.getElementById('search-status');
  const searchOutput = document.getElementById('global-search-results');
  const openSearchButtons = document.querySelectorAll('.open-global-search');

  let searchWorker = null;
  let searchReady = false;
  let pendingQuery = '';
  let requestId = 0;
  let latestRequest = 0;
  let searchTimer = null;
  let selectedResult = -1;

  function setSearchStatus(message) {
    if (searchStatus) searchStatus.textContent = message;
  }

  function ensureSearchWorker() {
    if (searchWorker || !window.Worker) {
      if (!window.Worker) setSearchStatus(pt ? 'Este navegador não oferece suporte ao mecanismo de busca.' : 'This browser does not support the search engine.');
      return;
    }

    setSearchStatus(pt ? 'Carregando índice de busca…' : 'Loading search index…');
    const workerUrl = new URL('assets/search-worker.js', root);
    const indexUrl = new URL('search/reader-' + lang + '.json', root);

    try {
      searchWorker = new Worker(workerUrl);
    } catch (error) {
      setSearchStatus(pt ? 'Não foi possível iniciar a busca.' : 'Could not start search.');
      return;
    }

    searchWorker.addEventListener('message', event => {
      const data = event.data || {};
      if (data.type === 'ready') {
        searchReady = true;
        setSearchStatus(pt ? 'Índice pronto. ' + data.count + ' entradas pesquisáveis.' : 'Index ready. ' + data.count + ' searchable entries.');
        if (pendingQuery) runSearch(pendingQuery);
      } else if (data.type === 'results') {
        if (data.requestId !== latestRequest) return;
        renderSearchResults(data.results || [], data.query || '');
      } else if (data.type === 'error') {
        setSearchStatus(pt ? 'Busca indisponível: ' + data.message : 'Search unavailable: ' + data.message);
      }
    });

    searchWorker.addEventListener('error', () => {
      searchReady = false;
      setSearchStatus(pt ? 'Falha ao carregar o mecanismo de busca.' : 'Failed to load search engine.');
    });

    searchWorker.postMessage({type:'init', indexUrl:indexUrl.href});
  }

  function openSearch() {
    if (!searchDialog) return;
    closeNav(false);
    searchDialog.hidden = false;
    body.classList.add('search-open');
    searchToggle && searchToggle.setAttribute('aria-expanded', 'true');
    ensureSearchWorker();
    requestAnimationFrame(() => searchInput && searchInput.focus());
  }

  function closeSearch(restoreFocus) {
    if (!searchDialog) return;
    searchDialog.hidden = true;
    body.classList.remove('search-open');
    searchToggle && searchToggle.setAttribute('aria-expanded', 'false');
    if (restoreFocus && searchToggle) searchToggle.focus({preventScroll:true});
  }

  searchToggle && searchToggle.addEventListener('click', openSearch);
  searchClose && searchClose.addEventListener('click', () => closeSearch(true));
  openSearchButtons.forEach(button => button.addEventListener('click', openSearch));
  searchDialog && searchDialog.addEventListener('click', event => {
    if (event.target === searchDialog) closeSearch(false);
  });

  function setSelected(index) {
    const links = searchOutput ? Array.from(searchOutput.querySelectorAll('.search-result')) : [];
    if (!links.length) {
      selectedResult = -1;
      return;
    }
    selectedResult = Math.max(0, Math.min(index, links.length - 1));
    links.forEach((link, i) => link.classList.toggle('is-selected', i === selectedResult));
    links[selectedResult].scrollIntoView({block:'nearest'});
  }

  function renderSearchResults(results, query) {
    if (!searchOutput) return;
    searchOutput.replaceChildren();
    selectedResult = -1;

    if (!results.length) {
      const empty = document.createElement('div');
      empty.className = 'search-empty';
      empty.textContent = pt ? 'Nenhum resultado para “' + query + '”.' : 'No results for “' + query + '”.';
      searchOutput.append(empty);
      setSearchStatus(pt ? '0 resultados.' : '0 results.');
      return;
    }

    const fragment = document.createDocumentFragment();
    results.forEach(result => {
      const link = document.createElement('a');
      link.className = 'search-result';
      link.setAttribute('role', 'option');
      link.href = new URL(result.location, root).href;

      const title = document.createElement('span');
      title.className = 'search-result-title';
      title.textContent = result.title || result.page_title || result.location;

      if (result.page_title && result.page_title !== result.title) {
        const context = document.createElement('span');
        context.className = 'search-result-context';
        context.textContent = result.page_title;
        link.append(title, context);
      } else {
        link.append(title);
      }

      if (result.snippet) {
        const snippet = document.createElement('span');
        snippet.className = 'search-result-snippet';
        snippet.textContent = result.snippet;
        link.append(snippet);
      }

      fragment.append(link);
    });

    searchOutput.append(fragment);
    setSearchStatus(pt ? results.length + ' resultados.' : results.length + ' results.');
  }

  function runSearch(query) {
    const value = String(query || '').trim();
    pendingQuery = value;
    if (!searchOutput) return;

    if (value.length < 2) {
      latestRequest = ++requestId;
      searchOutput.replaceChildren();
      setSearchStatus(pt ? 'Digite ao menos 2 caracteres.' : 'Type at least 2 characters.');
      return;
    }

    ensureSearchWorker();
    if (!searchReady || !searchWorker) {
      setSearchStatus(pt ? 'Preparando busca…' : 'Preparing search…');
      return;
    }

    pendingQuery = '';
    latestRequest = ++requestId;
    searchWorker.postMessage({type:'search', query:value, limit:36, requestId:latestRequest});
  }

  searchInput && searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    const value = searchInput.value;
    searchTimer = setTimeout(() => runSearch(value), 80);
  });

  searchInput && searchInput.addEventListener('keydown', event => {
    const links = searchOutput ? Array.from(searchOutput.querySelectorAll('.search-result')) : [];
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setSelected(selectedResult + 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setSelected(selectedResult <= 0 ? links.length - 1 : selectedResult - 1);
    } else if (event.key === 'Enter' && links.length) {
      event.preventDefault();
      const target = selectedResult >= 0 ? links[selectedResult] : links[0];
      target && target.click();
    }
  });

  document.addEventListener('keydown', event => {
    const target = event.target;
    const typing = target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement ||
      target instanceof HTMLSelectElement ||
      (target && target.isContentEditable);

    if (event.key === '/' && !typing && searchDialog && searchDialog.hidden) {
      event.preventDefault();
      openSearch();
    }

    if (event.key === 'Escape') {
      if (searchDialog && !searchDialog.hidden) closeSearch(true);
      else if (navPanel && navPanel.classList.contains('is-open')) closeNav(true);
    }
  });

  const tocLinks = Array.from(document.querySelectorAll('.chapter-rail a[href^="#"], .mobile-page-toc a[href^="#"]'));
  const tocTargets = [];
  tocLinks.forEach(link => {
    const hash = link.getAttribute('href');
    if (!hash || hash === '#') return;
    let id = '';
    try { id = decodeURIComponent(hash.slice(1)); } catch { id = hash.slice(1); }
    const target = document.getElementById(id);
    if (target) tocTargets.push({target, link});
  });

  let tocTicking = false;
  function updateActiveToc() {
    tocTicking = false;
    if (!tocTargets.length) return;
    let active = null;
    for (const item of tocTargets) {
      if (item.target.getBoundingClientRect().top <= 110) active = item.target;
      else break;
    }
    tocLinks.forEach(link => link.classList.remove('active-section'));
    if (!active && tocTargets.length) active = tocTargets[0].target;
    tocTargets.filter(item => item.target === active).forEach(item => item.link.classList.add('active-section'));
  }

  if (tocTargets.length) {
    updateActiveToc();
    addEventListener('scroll', () => {
      if (tocTicking) return;
      tocTicking = true;
      requestAnimationFrame(updateActiveToc);
    }, {passive:true});
  }

  document.querySelectorAll('.mobile-page-toc a[href^="#"]').forEach(link => {
    link.addEventListener('click', () => {
      const details = link.closest('details');
      if (details) details.open = false;
    });
  });

  document.querySelectorAll('article table').forEach(table => {
    if (table.parentElement && table.parentElement.classList.contains('table-scroll')) return;
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
