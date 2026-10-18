/* Implicit Communication literature index - viewer logic (vanilla JS, data from assets/data.js) */
(() => {
  'use strict';
  const D = window.LIT;
  if (!D) {
    document.querySelector('main').innerHTML =
      '<p class="empty">缺少 <code>assets/data.js</code>，请先在 paper/ 下运行 <code>python3 tools/build_site.py</code>。</p>';
    return;
  }

  /* ---------- helpers ---------- */
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const split = s => (s || '').split(';').map(x => x.trim()).filter(Boolean);
  const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode etc. */ } },
  };

  const TABS = ['index', 'review', 'directions', 'coding', 'forum', 'notes', 'incident', 'method'];
  const NOTES = D.notes || {};
  const TAX = D.taxonomy;
  const TAXMAP = Object.fromEntries(TAX.map(t => [t.code, t]));
  const catVar = c => `var(--c-${c})`;
  const CONTRIB_ZH = { method: '方法', benchmark: 'Benchmark', dataset: '数据集', metric: '指标', empirical: '实证研究',
    theory: '理论', survey: '综述', position: '立场', system: '系统', report: '技术报告' };
  const CHANNEL_ZH = Object.fromEntries(D.spectrum.map(s => [s.code, s.zh]));
  const TRAIN_ZH = { 'training-free': '免训练', SFT: 'SFT', RL: 'RL', other: '其他训练', 'n/a': '不适用' };
  const REL_ZH = { core: '核心', adjacent: '相邻', background: '背景' };
  const STATUS_ZH = { published: '已发表', accepted: '已录用', workshop: 'Workshop', preprint: '预印本', report: '技术报告' };
  const OPEN_ZH = { code: '开源代码', data: '开源数据', pdf: '本地 PDF' };
  const TOP_GROUPS = new Set(['ACL', 'EMNLP', 'NAACL', 'NeurIPS', 'ICML', 'ICLR']);
  const VENUE_GROUPS = ['NeurIPS', 'ICML', 'ICLR', 'ACL', 'EMNLP', 'NAACL', 'EACL', 'COLM', 'AAAI', 'TMLR', 'Other', 'arXiv'];
  const WINDOW_START = '2025-06';
  const WINDOW_END = '2026-10';

  function venueGroup(v) {
    const s = (v || '').trim();
    if (!s || /^arxiv$/i.test(s)) return 'arXiv';
    for (const g of ['NAACL', 'EACL', 'EMNLP', 'ACL', 'NeurIPS', 'ICML', 'ICLR', 'COLM', 'AAAI', 'TMLR']) {
      if (new RegExp(`\\b${g}\\b`, 'i').test(s)) return g;
    }
    return 'Other';
  }

  const P = D.papers.map(p => {
    const vg = venueGroup(p.venue);
    const open = [];
    if (p.code_open === 'yes') open.push('code');
    if (p.data_open === 'yes') open.push('data');
    if (p.pdf_file) open.push('pdf');
    return {
      ...p, vg, open, month: p.date.slice(0, 7),
      top: TOP_GROUPS.has(vg) && ['published', 'accepted'].includes(p.venue_status),
      contribs: split(p.contribution_types), channels: split(p.channel), secs: split(p.secondary_categories),
      tagList: split(p.tags), hasNote: Boolean(NOTES[p.id]),
      hay: [p.id, p.title, p.short_name, p.authors, p.summary_zh, p.core_contribution_zh, p.tags, p.venue,
        p.subcategory, p.notes, p.arxiv_id].join(' ').toLowerCase(),
    };
  });
  const BY_ID = Object.fromEntries(P.map(p => [p.id, p]));
  const TAX_ORDER = Object.fromEntries(TAX.map((t, i) => [t.code, i]));
  const NOTE_IDS = Object.keys(NOTES).filter(id => BY_ID[id]).sort((a, b) =>
    (TAX_ORDER[BY_ID[a].category] - TAX_ORDER[BY_ID[b].category]) || BY_ID[a].date.localeCompare(BY_ID[b].date));

  const FACETS = [
    { key: 'pick', title: '精选', values: ['must-read', 'deep-read', 'coding'],
      label: v => ({ 'must-read': '★ 推荐先读', 'deep-read': '已精读', coding: 'Coding 相关' }[v]),
      get: p => [...(p.tagList.includes('must-read') ? ['must-read'] : []), ...(p.hasNote ? ['deep-read'] : []),
        ...(p.tagList.includes('coding') || p.category === 'coding-mas' || p.secs.includes('coding-mas') ? ['coding'] : [])] },
    { key: 'cat', title: '类别（含次类别）', values: TAX.map(t => t.code), label: v => TAXMAP[v].zh, get: p => [p.category, ...p.secs], dot: true },
    { key: 'contrib', title: '贡献类型', values: Object.keys(CONTRIB_ZH), label: v => CONTRIB_ZH[v], get: p => p.contribs },
    { key: 'venue', title: '发表于', values: VENUE_GROUPS, label: v => (v === 'Other' ? '其他' : v), get: p => [p.vg] },
    { key: 'status', title: '发表状态', values: Object.keys(STATUS_ZH), label: v => STATUS_ZH[v], get: p => [p.venue_status] },
    { key: 'channel', title: '信道', values: D.spectrum.map(s => s.code), label: v => CHANNEL_ZH[v], get: p => p.channels },
    { key: 'training', title: '训练方式', values: Object.keys(TRAIN_ZH), label: v => TRAIN_ZH[v], get: p => [p.training] },
    { key: 'open', title: '开放资源（同时满足）', values: Object.keys(OPEN_ZH), label: v => OPEN_ZH[v], get: p => p.open, all: true },
    { key: 'rel', title: '相关性', values: Object.keys(REL_ZH), label: v => REL_ZH[v], get: p => [p.relevance] },
  ];

  /* ---------- state <-> URL hash ---------- */
  const S = { tab: 'index', note: '', q: '', f: {}, from: '', to: '', bg: false, sort: 'date-desc', view: 'cards' };
  FACETS.forEach(f => { S.f[f.key] = new Set(); });

  function writeHash() {
    const h = new URLSearchParams();
    if (S.tab !== 'index') h.set('tab', S.tab);
    if (S.tab === 'notes' && S.note) h.set('note', S.note);
    if (S.q) h.set('q', S.q);
    FACETS.forEach(f => { if (S.f[f.key].size) h.set(f.key, [...S.f[f.key]].join(',')); });
    if (S.from) h.set('from', S.from);
    if (S.to) h.set('to', S.to);
    if (S.bg) h.set('bg', '1');
    if (S.sort !== 'date-desc') h.set('sort', S.sort);
    if (S.view !== 'cards') h.set('view', S.view);
    const str = h.toString();
    history.replaceState(null, '', str ? `#${str}` : location.pathname + location.search);
  }

  function readHash() {
    const raw = location.hash.slice(1);
    if (raw.startsWith('paper:')) { openPaper(decodeURIComponent(raw.slice(6))); return; }
    if (raw.startsWith('note:')) { S.tab = 'notes'; S.note = decodeURIComponent(raw.slice(5)); return; }
    const h = new URLSearchParams(raw);
    S.tab = TABS.includes(h.get('tab')) ? h.get('tab') : 'index';
    S.note = h.get('note') || '';
    S.q = h.get('q') || '';
    FACETS.forEach(f => { S.f[f.key] = new Set(split((h.get(f.key) || '').replace(/,/g, ';'))); });
    S.from = h.get('from') || '';
    S.to = h.get('to') || '';
    S.bg = h.get('bg') === '1';
    S.sort = h.get('sort') || 'date-desc';
    S.view = h.get('view') === 'table' ? 'table' : 'cards';
  }

  /* ---------- filtering ---------- */
  function match(p, skip) {
    if (!S.bg && p.in_window === 'no') return false;
    if (skip !== 'date') {
      if (S.from && p.month < S.from) return false;
      if (S.to && p.month > S.to) return false;
    }
    for (const f of FACETS) {
      if (f.key === skip) continue;
      const sel = S.f[f.key];
      if (!sel.size) continue;
      const vals = f.get(p);
      const ok = f.all ? [...sel].every(v => vals.includes(v)) : vals.some(v => sel.has(v));
      if (!ok) return false;
    }
    if (S.q) {
      const terms = S.q.toLowerCase().split(/\s+/).filter(Boolean);
      if (!terms.every(t => p.hay.includes(t))) return false;
    }
    return true;
  }
  const filtered = skip => P.filter(p => match(p, skip));
  const activeCount = () => FACETS.reduce((n, f) => n + S.f[f.key].size, 0) + (S.from ? 1 : 0) + (S.to ? 1 : 0) + (S.q ? 1 : 0);

  function sortPapers(list) {
    const by = {
      'date-desc': (a, b) => b.date.localeCompare(a.date) || a.title.localeCompare(b.title),
      'date-asc': (a, b) => a.date.localeCompare(b.date) || a.title.localeCompare(b.title),
      title: (a, b) => a.title.localeCompare(b.title),
      venue: (a, b) => VENUE_GROUPS.indexOf(a.vg) - VENUE_GROUPS.indexOf(b.vg) || b.date.localeCompare(a.date),
      category: (a, b) => TAX.findIndex(t => t.code === a.category) - TAX.findIndex(t => t.code === b.category) || b.date.localeCompare(a.date),
    }[S.sort] || ((a, b) => b.date.localeCompare(a.date));
    return [...list].sort(by);
  }

  function hl(text) {
    let out = esc(text);
    if (!S.q) return out;
    const terms = S.q.split(/\s+/).filter(t => t.length > 1).map(t => esc(t).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    if (!terms.length) return out;
    return out.replace(new RegExp(`(${terms.join('|')})`, 'gi'), '<mark>$1</mark>');
  }

  /* ---------- overview: stats, spectrum, timeline, taxonomy ---------- */
  function renderStats() {
    const inW = P.filter(p => p.in_window === 'yes');
    const core = inW.filter(p => p.relevance === 'core').length;
    const top = inW.filter(p => p.top).length;
    const code = inW.filter(p => p.code_open === 'yes').length;
    const pdf = P.filter(p => p.pdf_file).length;
    const latest = inW.reduce((m, p) => (p.date > m ? p.date : m), '');
    const tiles = [
      [inW.length, '窗口内论文', `另含 ${P.length - inW.length} 篇窗口外背景文献`],
      [core, '核心：非文字信道', 'latent / KV-cache / parameter'],
      [top, '顶会已发表 / 录用', 'ACL·EMNLP·NAACL·NeurIPS·ICML·ICLR'],
      [`${pct(code, inW.length)}%`, '开源代码', `${code} / ${inW.length} 篇有可访问仓库`],
      [pdf, '本地 PDF', '位于 pdf/ 目录'],
      [latest || '—', '最近一篇', `索引构建于 ${D.built}`],
    ];
    $('#stats').innerHTML = tiles.map(([n, l, s]) =>
      `<div class="stat"><div class="num">${esc(n)}</div><div class="lbl">${esc(l)}</div><div class="sub">${esc(s)}</div></div>`).join('');
  }

  function renderSpectrum() {
    const base = filtered('channel');
    const n = D.spectrum.length;
    const segs = D.spectrum.map((s, i) => {
      const c = base.filter(p => p.channels.includes(s.code)).length;
      const k = i / (n - 1);
      const on = S.f.channel.has(s.code);
      return `<button class="seg-ch${on ? ' on' : ''}${c ? '' : ' zero'}${k > 0.55 ? ' dark-ink' : ''}" type="button"
        data-channel="${s.code}" style="--w:${(Math.sqrt(c) + 1).toFixed(2)};--k:${k.toFixed(2)}"
        title="${esc(s.zh)} (${s.code})：${c} 篇"><span class="n">${c}</span><span class="t">${esc(s.zh)}</span></button>`;
    }).join('');
    $('#spectrum').innerHTML =
      `<div class="spectrum-axis"><span><b>显式</b> · 人类可读</span><span>机器原生 · <b>隐式</b></span></div>
       <div class="spectrum">${segs}</div>
       <p class="spectrum-note">宽度 ∝ √篇数；颜色越深越远离自然语言。“无信道”指完全不发消息的协调（ToM、Schelling point）。</p>`;
  }

  function monthsRange() {
    const out = [];
    let [y, m] = WINDOW_START.split('-').map(Number);
    const [ey, em] = WINDOW_END.split('-').map(Number);
    while (y < ey || (y === ey && m <= em)) {
      out.push(`${y}-${String(m).padStart(2, '0')}`);
      m += 1; if (m > 12) { m = 1; y += 1; }
    }
    return out;
  }
  const MONTHS = monthsRange();

  function renderTimeline() {
    const base = filtered('date');
    const buckets = (S.bg ? ['早于窗口'] : []).concat(MONTHS);
    const data = buckets.map(b => {
      const rows = base.filter(p => (b === '早于窗口' ? p.month < WINDOW_START : p.month === b));
      return { b, rows, byCat: TAX.map(t => rows.filter(p => p.category === t.code).length) };
    });
    const max = Math.max(1, ...data.map(d => d.rows.length));
    const W = 640, H = 190, padL = 26, padB = 30, padT = 8;
    const bw = (W - padL - 6) / buckets.length;
    const y = v => H - padB - ((H - padB - padT) * v) / max;
    const ticks = [...new Set([0, Math.round(max / 2), max])];
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="按月发表数量">`;
    svg += '<g class="grid">' + ticks.map(t => `<line x1="${padL}" x2="${W}" y1="${y(t)}" y2="${y(t)}"/>`).join('') + '</g>';
    svg += '<g class="axis">' + ticks.map(t => `<text x="${padL - 6}" y="${y(t) + 3}" text-anchor="end">${t}</text>`).join('') + '</g>';
    data.forEach((d, i) => {
      const x = padL + i * bw + 2;
      const sel = d.b !== '早于窗口' && S.from && S.to && d.b >= S.from && d.b <= S.to;
      if (sel) svg += `<rect class="sel" x="${x - 2}" y="${padT}" width="${bw}" height="${H - padB - padT}" rx="4"/>`;
      let acc = 0;
      svg += `<g class="bar" data-month="${d.b}">`;
      svg += `<rect x="${x}" y="${padT}" width="${bw - 4}" height="${H - padB - padT}" fill="transparent"><title>${d.b}：${d.rows.length} 篇</title></rect>`;
      d.byCat.forEach((c, ci) => {
        if (!c) return;
        const y1 = y(acc + c), h = y(acc) - y1;
        svg += `<rect x="${x}" y="${y1}" width="${Math.max(2, bw - 4)}" height="${Math.max(0, h - 1)}" rx="2" fill="${catVar(TAX[ci].code)}"><title>${d.b} · ${esc(TAX[ci].zh)}：${c}</title></rect>`;
        acc += c;
      });
      svg += '</g>';
      const lbl = d.b === '早于窗口' ? '更早' : `${d.b.slice(2, 4)}.${d.b.slice(5)}`;
      svg += `<g class="axis"><text x="${x + (bw - 4) / 2}" y="${H - padB + 14}" text-anchor="middle">${lbl}</text></g>`;
    });
    svg += '</svg>';
    const legend = TAX.map(t => `<span><i style="background:${catVar(t.code)}"></i>${esc(t.zh)}</span>`).join('');
    $('#timeline').innerHTML = `<div class="timeline">${svg}</div><div class="legend">${legend}</div>`;
  }

  function renderTaxonomy() {
    const vis = P.filter(p => S.bg || p.in_window === 'yes');
    $('#taxonomy').innerHTML = TAX.map(t => {
      const prim = vis.filter(p => p.category === t.code);
      const cross = vis.filter(p => p.category !== t.code && p.secs.includes(t.code)).length;
      const ct = {};
      prim.forEach(p => p.contribs.forEach(c => { ct[c] = (ct[c] || 0) + 1; }));
      const topCt = Object.entries(ct).sort((a, b) => b[1] - a[1]).slice(0, 3)
        .map(([k, v]) => `${CONTRIB_ZH[k] || k} ${v}`).join(' · ');
      const code = prim.filter(p => p.code_open === 'yes').length;
      return `<button class="tax${S.f.cat.has(t.code) ? ' on' : ''}" type="button" data-cat="${t.code}" style="--cat:${catVar(t.code)}">
        <div class="row"><div><h3>${esc(t.zh)}</h3><div class="en">${esc(t.en)}</div></div><div class="count">${prim.length}</div></div>
        <p>${esc(t.desc)}</p>
        <div class="row" style="align-items:center"><span class="tier ${t.tier}">${REL_ZH[t.tier]}</span>
          <span class="hint">${topCt || '—'}${cross ? ` · 交叉 +${cross}` : ''}${prim.length ? ` · 开源 ${code}` : ''}</span></div>
      </button>`;
    }).join('');
  }

  /* ---------- filters panel ---------- */
  function renderFilters() {
    const months = [...new Set(P.filter(p => S.bg || p.in_window === 'yes').map(p => p.month))].sort();
    const opt = (v, cur) => `<option value="${v}"${v === cur ? ' selected' : ''}>${v || '不限'}</option>`;
    let html = FACETS.map(f => {
      const base = filtered(f.key);
      const chips = f.values.map(v => {
        const c = base.filter(p => f.get(p).includes(v)).length;
        const on = S.f[f.key].has(v);
        if (!c && !on && f.key !== 'cat') return '';
        return `<button class="chip${on ? ' on' : ''}${c ? '' : ' zero'}" type="button" data-facet="${f.key}" data-v="${esc(v)}"
          ${f.dot ? `style="--cat:${catVar(v)}"` : ''}>${f.dot ? '<span class="dot"></span>' : ''}${esc(f.label(v))}<span class="c">${c}</span></button>`;
      }).join('');
      return chips ? `<div class="facet"><h4>${esc(f.title)}</h4><div class="chips">${chips}</div></div>` : '';
    }).join('');
    html += `<div class="facet"><h4>时间范围（首个 arXiv 版本）</h4>
      <div class="range"><select id="from">${['', ...months].map(m => opt(m, S.from)).join('')}</select>
      <span>→</span><select id="to">${['', ...months].map(m => opt(m, S.to)).join('')}</select></div>
      <label class="toggle"><input type="checkbox" id="bg"${S.bg ? ' checked' : ''}> 显示窗口外的奠基 / 背景文献</label></div>
      <button class="btn full" id="reset" type="button">清除全部筛选</button>`;
    $('#filters').innerHTML = html;
    $('#active-count').textContent = activeCount() || '';
  }

  /* ---------- results ---------- */
  function linksHtml(p, withMore = true) {
    const paper = p.paper_url || (p.arxiv_id ? `https://arxiv.org/abs/${p.arxiv_id}` : '');
    const parts = [];
    if (paper) parts.push(`<a class="lk" href="${esc(paper)}" target="_blank" rel="noopener">${p.arxiv_id ? 'arXiv' : '论文'} ↗</a>`);
    parts.push(p.pdf_file
      ? `<a class="lk" href="${esc(p.pdf_file)}" target="_blank" rel="noopener">PDF</a>`
      : '<span class="lk off">PDF</span>');
    if (p.code_url) parts.push(`<a class="lk${p.code_open === 'yes' ? ' code' : ''}" href="${esc(p.code_url)}" target="_blank" rel="noopener">Code${p.code_open === 'announced' ? '（待放出）' : ''} ↗</a>`);
    else parts.push('<span class="lk off">无代码</span>');
    if (p.data_url) parts.push(`<a class="lk" href="${esc(p.data_url)}" target="_blank" rel="noopener">Data ↗</a>`);
    if (p.hasNote) parts.push(`<button class="lk note" type="button" data-note="${esc(p.id)}">精读笔记</button>`);
    if (withMore) parts.push(`<button class="lk more" type="button" data-open="${esc(p.id)}">详情</button>`);
    return parts.join('');
  }

  function venueBadge(p) {
    const cls = p.top ? 'venue top' : (p.venue_status === 'preprint' ? 'venue pre' : 'venue');
    const st = ['workshop', 'accepted'].includes(p.venue_status) ? ` · ${STATUS_ZH[p.venue_status]}` : '';
    return `<span class="${cls}">${esc(p.venue || 'arXiv')}${st}</span>`;
  }

  function card(p) {
    const t = TAXMAP[p.category] || { zh: p.category };
    const badges = p.contribs.map(c => `<span class="badge ct">${esc(CONTRIB_ZH[c] || c)}</span>`)
      .concat(p.channels.map(c => `<span class="badge ch">${esc(CHANNEL_ZH[c] || c)}</span>`))
      .concat(p.training && p.training !== 'n/a' ? [`<span class="badge">${esc(TRAIN_ZH[p.training] || p.training)}</span>`] : [])
      .concat(p.in_window === 'no' ? ['<span class="badge bg">窗口外</span>'] : []);
    const author = p.first_author || (p.authors || '').split(/[;,]/)[0];
    return `<article class="card" style="--cat:${catVar(p.category)}">
      <div class="card-top"><span class="cat-pill">${esc(t.zh)}</span>${venueBadge(p)}${p.tagList.includes('must-read') ? '<span class="star" title="推荐先读">★</span>' : ''}${p.hasNote ? '<span class="rd" title="已精读，有笔记">精读</span>' : ''}<span class="date">${esc(p.date)}</span></div>
      <h3><a href="#paper:${encodeURIComponent(p.id)}" data-open="${esc(p.id)}">${hl(p.title)}</a></h3>
      <div class="meta">${p.short_name ? `<b>${hl(p.short_name)}</b> · ` : ''}${esc(author)}${p.authors && p.authors.includes(';') ? ' 等' : ''}</div>
      <p class="summary">${hl(p.summary_zh)}</p>
      <div class="badges">${badges.join('')}</div>
      <div class="links">${linksHtml(p)}</div>
    </article>`;
  }

  function table(list) {
    const rows = list.map(p => `<tr style="--cat:${catVar(p.category)}">
      <td class="nowrap">${esc(p.date)}</td>
      <td><span class="t" data-open="${esc(p.id)}">${hl(p.short_name || p.title)}</span>${p.hasNote ? ` <a class="rd" href="#" data-note="${esc(p.id)}" title="打开精读笔记">精读</a>` : ''}<div class="s">${hl(p.title)}</div></td>
      <td class="nowrap"><span class="catdot"></span>${esc((TAXMAP[p.category] || {}).zh || p.category)}</td>
      <td>${hl(p.summary_zh)}</td>
      <td>${p.contribs.map(c => esc(CONTRIB_ZH[c] || c)).join(' / ')}</td>
      <td class="nowrap">${venueBadge(p)}</td>
      <td class="nowrap">${p.code_open === 'yes' ? `<a href="${esc(p.code_url)}" target="_blank" rel="noopener">✓ code</a>` : (p.code_open === 'announced' ? '待放出' : '—')}${p.data_open === 'yes' ? ' · data' : ''}</td>
      <td class="nowrap">${p.pdf_file ? `<a href="${esc(p.pdf_file)}" target="_blank" rel="noopener">PDF</a>` : '—'}</td>
    </tr>`).join('');
    return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>日期</th><th>论文</th><th>类别</th><th>一句话摘要</th><th>贡献</th><th>Venue</th><th>开源</th><th>PDF</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  function renderResults() {
    const list = sortPapers(filtered());
    const hidden = S.bg ? 0 : P.filter(p => p.in_window === 'no').length;
    $('#result-count').textContent = `${list.length} / ${P.length - hidden} 篇`;
    $$('.seg [data-view]').forEach(b => b.classList.toggle('on', b.dataset.view === S.view));
    $('#sort').value = S.sort;
    if ($('#q') !== document.activeElement) $('#q').value = S.q;
    $('#results').innerHTML = !list.length
      ? '<div class="empty">没有符合条件的论文。试试清除部分筛选，或打开“显示窗口外的背景文献”。</div>'
      : (S.view === 'table' ? table(list) : `<div class="cards">${list.map(card).join('')}</div>`);
  }

  /* ---------- modal ---------- */
  function openPaper(id) {
    const p = BY_ID[id];
    if (!p) return;
    const t = TAXMAP[p.category] || { zh: p.category };
    const row = (k, v) => (v ? `<dt>${k}</dt><dd>${v}</dd>` : '');
    const link = u => (u ? `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u)}</a>` : '');
    $('#modal-body').innerHTML = `<div class="modal" style="--cat:${catVar(p.category)}">
      <button class="close" type="button" aria-label="关闭" data-close>✕</button>
      <div class="card-top"><span class="cat-pill">${esc(t.zh)}</span>${venueBadge(p)}<span class="date">${esc(p.date)}</span></div>
      <h2>${esc(p.title)}</h2>
      <div class="meta muted">${esc(p.authors)}</div>
      <p class="summary">${esc(p.summary_zh)}</p>
      <dl>
        ${row('核心贡献', esc(p.core_contribution_zh))}
        ${row('贡献类型', p.contribs.map(c => esc(CONTRIB_ZH[c] || c)).join(' · '))}
        ${row('子类别', esc(p.subcategory))}
        ${row('次类别', p.secs.map(c => esc((TAXMAP[c] || {}).zh || c)).join(' · '))}
        ${row('信道', p.channels.map(c => esc(CHANNEL_ZH[c] || c)).join(' · '))}
        ${row('训练方式', esc(TRAIN_ZH[p.training] || p.training))}
        ${row('跨异构模型', esc({ yes: '支持', no: '仅同构', 'n/a': '不适用' }[p.heterogeneous] || p.heterogeneous))}
        ${row('相关性', esc(`${REL_ZH[p.relevance] || p.relevance}${p.in_window === 'no' ? '（窗口外）' : ''}`))}
        ${row('发表状态', `${esc(STATUS_ZH[p.venue_status] || p.venue_status)}${p.venue_evidence ? ` · <a href="${esc(p.venue_evidence)}" target="_blank" rel="noopener">证据</a>` : ''}`)}
        ${row('代码', p.code_url ? `${link(p.code_url)}（${esc(p.code_open)}）` : esc(p.code_open === 'no' ? '未找到公开代码' : p.code_open))}
        ${row('数据', p.data_url ? `${link(p.data_url)}（${esc(p.data_open)}）` : '')}
        ${row('标签', p.tagList.map(esc).join(' · '))}
        ${row('备注', esc(p.notes))}
        ${row('核实', esc(p.verified))}
        ${row('ID', `<code>${esc(p.id)}</code>${p.arxiv_id ? ` · arXiv:${esc(p.arxiv_id)}` : ''}`)}
      </dl>
      <div class="links" style="margin-top:16px">${linksHtml(p, false)}</div>
    </div>`;
    const dlg = $('#paper-modal');
    if (!dlg.open) dlg.showModal();
  }

  /* ---------- markdown docs ---------- */
  const slug = (s, used) => {
    let base = s.trim().toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '') || 'sec';
    let id = base, i = 2;
    while (used.has(id)) id = `${base}-${i++}`;
    used.add(id);
    return id;
  };

  function renderDoc(md, docSel, tocSel, extraHtml = '') {
    const doc = $(docSel), toc = tocSel ? $(tocSel) : null;
    if (!md && !extraHtml) { doc.innerHTML = '<p class="muted">（尚未生成）</p>'; if (toc) toc.innerHTML = ''; return []; }
    doc.innerHTML = (window.marked ? window.marked.parse(md || '') : `<pre>${esc(md)}</pre>`) + extraHtml;
    const used = new Set();
    const heads = $$('h2, h3', doc);
    heads.forEach(h => { h.id = slug(`${docSel}-${h.textContent}`, used); });
    if (toc) toc.innerHTML = heads.map(h => `<a class="${h.tagName.toLowerCase()}" href="#" data-target="${h.id}">${esc(h.textContent)}</a>`).join('');
    $$('a[href^="#paper:"]', doc).forEach(a => {
      const id = decodeURIComponent(a.getAttribute('href').slice(7));
      a.classList.add('pref');
      a.dataset.open = id;
      if (BY_ID[id]) a.title = BY_ID[id].title;
      else a.title = `（索引中未找到 ${id}）`;
    });
    $$('a[href^="#note:"]', doc).forEach(a => {
      const id = decodeURIComponent(a.getAttribute('href').slice(6));
      a.classList.add('nref');
      a.dataset.note = id;
      a.title = NOTES[id] ? `精读笔记：${BY_ID[id]?.title || id}` : `（没有 ${id} 的精读笔记）`;
    });
    $$('a[href^="http"]', doc).forEach(a => { a.target = '_blank'; a.rel = 'noopener'; });
    return heads;
  }

  /* ---------- deep-reading notes ---------- */
  function renderNotes() {
    const nav = $('#notes-nav'), sel = $('#note-select'), doc = $('#notes-doc');
    if (!NOTE_IDS.length) { nav.innerHTML = ''; sel.innerHTML = ''; doc.innerHTML = '<p class="muted">（尚无精读笔记）</p>'; return; }
    if (!NOTES[S.note]) S.note = NOTE_IDS[0];
    let last = '';
    nav.innerHTML = `<div class="nn-title">精读笔记 · ${NOTE_IDS.length} 篇</div>` + NOTE_IDS.map(id => {
      const p = BY_ID[id];
      const head = p.category !== last
        ? `<div class="nn-group" style="--cat:${catVar(p.category)}">${esc((TAXMAP[p.category] || {}).zh || p.category)}</div>` : '';
      last = p.category;
      return `${head}<a href="#" class="nn${id === S.note ? ' on' : ''}" data-note="${esc(id)}" style="--cat:${catVar(p.category)}"
        title="${esc(p.title)}">${esc(p.short_name || id)}</a>`;
    }).join('');
    sel.innerHTML = NOTE_IDS.map(id => `<option value="${esc(id)}"${id === S.note ? ' selected' : ''}>${
      esc(((TAXMAP[BY_ID[id].category] || {}).zh || '') + ' · ' + (BY_ID[id].short_name || id))}</option>`).join('');
    const p = BY_ID[S.note];
    const heads = renderDoc(NOTES[S.note], '#notes-doc', null);
    const i = NOTE_IDS.indexOf(S.note);
    const prev = NOTE_IDS[i - 1], next = NOTE_IDS[i + 1];
    doc.style.setProperty('--cat', catVar(p.category));
    doc.insertAdjacentHTML('afterbegin', `<div class="note-head">
      <div class="card-top"><span class="cat-pill">${esc((TAXMAP[p.category] || {}).zh || p.category)}</span>${venueBadge(p)}<span class="date">${esc(p.date)}</span></div>
      <div class="links">${linksHtml(p, false).replace(/<button class="lk note"[^>]*>[^<]*<\/button>/, '')}<button class="lk more" type="button" data-open="${esc(p.id)}">索引卡片</button></div>
      <div class="sec-chips">${heads.filter(h => h.tagName === 'H2').map(h =>
        `<a href="#" data-target="${h.id}">${esc(h.textContent.replace(/^\d+\.\s*/, ''))}</a>`).join('')}</div>
    </div>`);
    doc.insertAdjacentHTML('beforeend', `<div class="note-pager">
      ${prev ? `<a href="#" data-note="${esc(prev)}">← ${esc(BY_ID[prev].short_name || prev)}</a>` : '<span></span>'}
      ${next ? `<a href="#" data-note="${esc(next)}">${esc(BY_ID[next].short_name || next)} →</a>` : '<span></span>'}
    </div>`);
  }

  function gotoNote(id) {
    if ($('#paper-modal').open) $('#paper-modal').close();
    S.tab = 'notes';
    S.note = id;
    showTab(); // renders the note
    writeHash();
    window.scrollTo(0, 0);
  }

  /* ---------- research-direction map (difficulty x impact) ---------- */
  function directionsMapHtml(M) {
    if (!M || !M.length) return '';
    const W = 640, H = 380, L = 54, R = 20, T = 20, B = 46, PAD = 22;
    const x = v => L + PAD + ((v - 1) / 4) * (W - L - R - 2 * PAD);
    const y = v => H - B - PAD - ((v - 1) / 4) * (H - T - B - 2 * PAD);
    const KIND = { hard: '最有挑战', water: '容易出论文', core: '主线' };
    const grid = [1, 2, 3, 4, 5].map(v => `<line class="g" x1="${x(v)}" x2="${x(v)}" y1="${T}" y2="${H - B}"/><line class="g" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/>
      <text class="ax" x="${x(v)}" y="${H - B + 16}" text-anchor="middle">${v}</text><text class="ax" x="${L - 10}" y="${y(v) + 4}" text-anchor="end">${v}</text>`).join('');
    const dots = M.map(d => {
      const cx = x(d.difficulty) + (d.dx || 0), cy = y(d.impact) + (d.dy || 0);
      const r = 9 + 2.2 * (d.water || 0);
      return `<g class="dm ${esc(d.kind || 'core')}" data-target="${esc(d.anchor || '')}"><title>${esc(`${d.n}. ${d.title}\n难度 ${d.difficulty} · 影响 ${d.impact} · 灌水度 ${d.water}`)}</title>
        <circle cx="${cx}" cy="${cy}" r="${r}"/><text x="${cx}" y="${cy + 4}" text-anchor="middle">${esc(d.n)}</text>
        <text class="lbl" x="${cx > W * 0.7 ? cx - r - 4 : cx + r + 4}" y="${cy + 4}"${cx > W * 0.7 ? ' text-anchor="end"' : ''}>${esc(d.short || '')}</text></g>`;
    }).join('');
    return `<figure class="dmap"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="研究方向：难度 × 影响">
      ${grid}<text class="axt" x="${(L + W - R) / 2}" y="${H - 8}" text-anchor="middle">难度 →</text>
      <text class="axt" x="14" y="${(T + H - B) / 2}" text-anchor="middle" transform="rotate(-90 14 ${(T + H - B) / 2})">潜在影响 →</text>${dots}</svg>
      <figcaption>${Object.entries(KIND).map(([k, v]) => `<span class="dm-key ${k}"><i></i>${v}</span>`).join('')}<span class="muted">圆越大 = 越容易快速出论文（“灌水度”）</span></figcaption></figure>`;
  }

  function renderDirections(md, map, docSel, tocSel, slotSel) {
    renderDoc(md, docSel, tocSel);
    const doc = $(docSel), slot = $(slotSel, doc);
    if (slot) {
      slot.innerHTML = directionsMapHtml(map);
      // anchors in the map point at the direction headings; resolve them by heading text prefix
      $$('.dm', slot).forEach(g => {
        const h = $$('h2, h3', doc).find(e => new RegExp(`^${g.dataset.target}(?![0-9A-Za-z])`).test(e.textContent.trim()));
        if (h) g.dataset.target = h.id; else g.removeAttribute('data-target');
      });
    }
  }

  function coverageHtml() {
    const inW = P.filter(p => p.in_window === 'yes');
    const count = (list, f) => list.reduce((m, p) => { f(p).forEach(k => { m[k] = (m[k] || 0) + 1; }); return m; }, {});
    const tableOf = (title, obj, label) => {
      const rows = Object.entries(obj).sort((a, b) => b[1] - a[1])
        .map(([k, v]) => `<tr><td>${esc(label ? label(k) : k)}</td><td>${v}</td><td>${pct(v, inW.length)}%</td></tr>`).join('');
      return `<h3>${esc(title)}</h3><table><thead><tr><th>项</th><th>篇数</th><th>占窗口内</th></tr></thead><tbody>${rows}</tbody></table>`;
    };
    const fields = [
      ['id', '稳定主键（第一作者姓 + 年份 + 标题首词）'], ['short_name', '方法 / benchmark 简称'], ['date', '首个 arXiv 版本日期'],
      ['venue / venue_status', '发表处与状态（published / accepted / workshop / preprint / report）'], ['venue_evidence', 'venue 证据链接'],
      ['summary_zh', '一句话中文摘要'], ['contribution_types', '贡献类型（多值）'], ['core_contribution_zh', '核心新贡献'],
      ['category / secondary_categories', '主类别 / 次类别'], ['channel', '信道（多值）'], ['training', '是否需要训练'],
      ['heterogeneous', '是否支持跨异构模型'], ['code_url / code_open', '代码仓库与可用性（yes / announced / no）'],
      ['data_url / data_open', '数据与可用性'], ['relevance / in_window', '相关性层级 / 是否在时间窗口内'], ['verified', '核实记录'],
    ];
    return `<h2>覆盖统计（自动生成）</h2>
      ${tableOf('按发表处', count(inW, p => [p.vg]), k => (k === 'Other' ? '其他' : k))}
      ${tableOf('按主类别', count(inW, p => [p.category]), k => (TAXMAP[k] || {}).zh || k)}
      ${tableOf('按贡献类型', count(inW, p => p.contribs), k => CONTRIB_ZH[k] || k)}
      ${tableOf('开放资源', count(inW, p => p.open), k => OPEN_ZH[k] || k)}
      <h2>index.csv 字段说明</h2>
      <table><thead><tr><th>字段</th><th>含义</th></tr></thead><tbody>
      ${fields.map(([k, v]) => `<tr><td><code>${esc(k)}</code></td><td>${esc(v)}</td></tr>`).join('')}</tbody></table>`;
  }

  /* ---------- export ---------- */
  function exportCsv() {
    const cols = D.columns;
    const q = v => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const lines = [cols.join(',')].concat(sortPapers(filtered()).map(p => cols.map(c => q(p[c])).join(',')));
    const blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'index_filtered.csv';
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  /* ---------- tabs, theme, wiring ---------- */
  function showTab() {
    $$('.tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === S.tab));
    $$('.tab').forEach(s => s.classList.toggle('active', s.id === `tab-${S.tab}`));
    if (S.tab === 'notes') renderNotes();
  }

  function renderIndex() {
    renderSpectrum();
    renderTimeline();
    renderTaxonomy();
    renderFilters();
    renderResults();
  }
  function update() { renderIndex(); writeHash(); }

  function toggleSet(set, v) { if (set.has(v)) set.delete(v); else set.add(v); }

  function initTheme() {
    const saved = store.get('lit-theme');
    if (saved) document.documentElement.dataset.theme = saved;
    $('#theme-toggle').addEventListener('click', () => {
      const cur = document.documentElement.dataset.theme
        || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      const next = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
      store.set('lit-theme', next);
    });
  }

  function wire() {
    document.addEventListener('click', e => {
      const t = e.target.closest('[data-open],[data-note],[data-facet],[data-cat],[data-channel],[data-view],[data-tab],[data-close],[data-target],.bar,#reset,#export');
      if (!t) return;
      if (t.dataset.open) { e.preventDefault(); openPaper(t.dataset.open); return; }
      if (t.dataset.note) { e.preventDefault(); gotoNote(t.dataset.note); return; }
      if (t.dataset.close !== undefined) { $('#paper-modal').close(); return; }
      if (t.dataset.target) { e.preventDefault(); document.getElementById(t.dataset.target)?.scrollIntoView({ behavior: 'smooth' }); return; }
      if (t.dataset.tab) { S.tab = t.dataset.tab; showTab(); writeHash(); window.scrollTo(0, 0); return; }
      if (t.dataset.facet) toggleSet(S.f[t.dataset.facet], t.dataset.v);
      else if (t.dataset.cat) {
        toggleSet(S.f.cat, t.dataset.cat);
        if (t.dataset.cat === 'latent-reasoning-bg' && S.f.cat.has('latent-reasoning-bg')) S.bg = true;
      } else if (t.dataset.channel) toggleSet(S.f.channel, t.dataset.channel);
      else if (t.dataset.view) S.view = t.dataset.view;
      else if (t.classList.contains('bar')) {
        const m = t.dataset.month;
        if (m === '早于窗口') { S.from = ''; S.to = ''; }
        else if (S.from === m && S.to === m) { S.from = ''; S.to = ''; }
        else { S.from = m; S.to = m; }
      } else if (t.id === 'reset') {
        FACETS.forEach(f => S.f[f.key].clear());
        S.q = ''; S.from = ''; S.to = '';
      } else if (t.id === 'export') { exportCsv(); return; }
      update();
    });
    document.addEventListener('change', e => {
      if (e.target.id === 'note-select') { gotoNote(e.target.value); return; }
      if (e.target.id === 'from') S.from = e.target.value;
      else if (e.target.id === 'to') S.to = e.target.value;
      else if (e.target.id === 'bg') S.bg = e.target.checked;
      else if (e.target.id === 'sort') S.sort = e.target.value;
      else return;
      update();
    });
    let timer;
    $('#q').addEventListener('input', e => {
      clearTimeout(timer);
      timer = setTimeout(() => { S.q = e.target.value.trim(); update(); }, 150);
    });
    document.addEventListener('keydown', e => {
      if (e.key === '/' && !['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
        e.preventDefault();
        if (S.tab !== 'index') { S.tab = 'index'; showTab(); }
        $('#q').focus();
      }
    });
    $('#paper-modal').addEventListener('click', e => { if (e.target.id === 'paper-modal') e.target.close(); });
    window.addEventListener('hashchange', () => {
      if (location.hash.startsWith('#paper:')) { openPaper(decodeURIComponent(location.hash.slice(7))); return; }
      if (location.hash.startsWith('#note:')) { gotoNote(decodeURIComponent(location.hash.slice(6))); return; }
      readHash(); showTab(); renderIndex();
    });
    if (matchMedia('(max-width: 900px)').matches) $('#filters-drawer').open = false;
  }

  function init() {
    initTheme();
    readHash();
    renderStats();
    renderDoc(D.reviewMd, '#review-doc', '#review-toc');
    renderDoc(D.incidentMd + (D.sourcesMd ? `\n\n---\n\n${D.sourcesMd}` : ''), '#incident-doc', '#incident-toc');
    renderDoc(D.methodMd, '#method-doc', '#method-toc', coverageHtml());
    renderDirections(D.directionsMd, D.directionsMap, '#directions-doc', '#directions-toc', '#dir-map');
    renderDirections(D.codingMd, D.codingMap, '#coding-doc', '#coding-toc', '#coding-map');
    if (D.forumMd) renderDoc(D.forumMd, '#forum-doc', '#forum-toc');
    $('#built').textContent = `索引构建于 ${D.built} · ${P.length} 条记录`;
    wire();
    showTab();
    renderIndex();
  }

  init();
})();
