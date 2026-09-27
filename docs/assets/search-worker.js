let documents = [];
let ready = false;

function normalize(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase();
}

function snippetFor(doc, terms, firstIndex) {
  const raw = String(doc.text || '').replace(/\s+/g, ' ').trim();
  if (!raw) return '';
  const low = normalize(raw);
  let index = Number.isFinite(firstIndex) ? firstIndex : Infinity;
  if (!Number.isFinite(index)) {
    terms.forEach(term => {
      const found = low.indexOf(term);
      if (found >= 0) index = Math.min(index, found);
    });
  }
  if (!Number.isFinite(index)) index = 0;
  const start = Math.max(0, index - 85);
  const end = Math.min(raw.length, start + 230);
  return (start ? '…' : '') + raw.slice(start, end).trim() + (end < raw.length ? '…' : '');
}

function scoreDocument(doc, terms) {
  let score = 0;
  let firstIndex = Infinity;

  for (const term of terms) {
    let matched = false;

    if (doc._title === term) {
      score += 90;
      matched = true;
    } else if (doc._title.startsWith(term)) {
      score += 48;
      matched = true;
    } else if (doc._title.includes(term)) {
      score += 30;
      matched = true;
    }

    if (doc._pageTitle === term) {
      score += 42;
      matched = true;
    } else if (doc._pageTitle.includes(term)) {
      score += 16;
      matched = true;
    }

    if (doc._location.includes(term)) {
      score += 8;
      matched = true;
    }

    const textIndex = doc._text.indexOf(term);
    if (textIndex >= 0) {
      matched = true;
      firstIndex = Math.min(firstIndex, textIndex);
      score += Math.max(3, 13 - Math.floor(textIndex / 500));
    }

    if (!matched) return null;
  }

  if (doc.kind === 'page') score += 4;
  return {score, firstIndex};
}

async function initialize(indexUrl) {
  try {
    const response = await fetch(indexUrl, {cache:'force-cache'});
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const data = await response.json();
    documents = (data.docs || []).map(doc => ({
      ...doc,
      _title: normalize(doc.title),
      _pageTitle: normalize(doc.page_title),
      _location: normalize(doc.location),
      _text: normalize(doc.text)
    }));
    ready = true;
    postMessage({type:'ready', count:documents.length});
  } catch (error) {
    ready = false;
    postMessage({type:'error', message:error && error.message ? error.message : String(error)});
  }
}

function search(query, limit) {
  const terms = normalize(query).split(/\s+/).filter(Boolean);
  if (!terms.length) return [];

  const ranked = [];
  for (const doc of documents) {
    const score = scoreDocument(doc, terms);
    if (!score) continue;
    ranked.push({doc, score:score.score, firstIndex:score.firstIndex});
  }

  ranked.sort((a, b) =>
    b.score - a.score ||
    String(a.doc.page_title || '').localeCompare(String(b.doc.page_title || '')) ||
    String(a.doc.title || '').localeCompare(String(b.doc.title || ''))
  );

  const results = [];
  const seen = new Set();
  for (const item of ranked) {
    const baseLocation = String(item.doc.location || '').split('#', 1)[0];
    const key = baseLocation + '\\u0000' + item.doc._title;
    if (seen.has(key)) continue;
    seen.add(key);
    results.push({
      location:item.doc.location,
      title:item.doc.title,
      page_title:item.doc.page_title,
      kind:item.doc.kind,
      snippet:snippetFor(item.doc, terms, item.firstIndex)
    });
    if (results.length >= (limit || 36)) break;
  }
  return results;
}

self.onmessage = event => {
  const data = event.data || {};
  if (data.type === 'init') {
    initialize(data.indexUrl);
  } else if (data.type === 'search') {
    if (!ready) {
      postMessage({type:'error', message:'index-not-ready'});
      return;
    }
    const results = search(data.query || '', data.limit || 36);
    postMessage({type:'results', query:data.query || '', requestId:data.requestId, results});
  }
};
