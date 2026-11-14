// src/build.mjs — X2 NFL Lines static-site generator.
// Reads structured data (data/*.json) and narrative docs (docs/*.md),
// renders a dashboard-style static site into site/.
// No external dependencies — a small, self-contained generator.

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const DATA_DIR = join(ROOT, 'data');
const DOCS_DIR = join(ROOT, 'docs');
const SITE_DIR = join(ROOT, 'site');
const ASSETS_DIR = join(SITE_DIR, 'assets');

// ---------------------------------------------------------------------------
// Page registry
// ---------------------------------------------------------------------------
const PAGES = [
  { slug: 'executive-summary',      title: 'Executive Summary',   category: 'Overview', doc: '00-executive-summary.md' },
  { slug: 'requirements',           title: 'Requirements',        category: 'Planning', doc: '01-requirements.md' },
  { slug: 'questions-and-answers',  title: 'Questions & Answers', category: 'Planning', doc: '02-questions-and-answers.md' },
  { slug: 'suggestions',            title: 'Suggestions',         category: 'Planning', doc: '03-suggestions.md' },
  { slug: 'strategy-research',      title: 'Strategy Research',   category: 'Strategy', doc: '04-strategy-research.md' },
  { slug: 'validation-gates',       title: 'Validation Gates',    category: 'Strategy', doc: '05-validation-gates.md' },
  { slug: 'correlation',            title: 'Correlation Values',  category: 'Strategy', doc: '06-correlation.md' },
  { slug: 'leaderboard',            title: 'Strategy Leaderboard', category: 'Strategy', doc: '07-leaderboard.md' },
  { slug: 'injuries-and-depth',     title: 'Injuries & Depth',    category: 'Data',     doc: '08-injuries-and-depth.md' },
  { slug: 'data-sources',           title: 'Data Sources & Verification', category: 'Data', doc: '09-data-sources-and-verification.md' },
  { slug: 'flagged-for-review',     title: 'Flagged for Review',  category: 'Data',     doc: '10-flagged-for-review.md' },
];

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------
function loadJson(name) {
  const path = join(DATA_DIR, name);
  if (!existsSync(path)) return null;
  return JSON.parse(readFileSync(path, 'utf8'));
}

const sources = loadJson('sources.json') || {};
const data = {
  requirements: loadJson('requirements.json'),
  questions: loadJson('questions.json'),
  suggestions: loadJson('suggestions.json'),
  strategies: loadJson('strategies.json'),
  validationGates: loadJson('validation-gates.json'),
  correlations: loadJson('correlations.json'),
  leaderboard: loadJson('leaderboard.json'),
  injuries: loadJson('injuries.json'),
  depthDeficiencies: loadJson('depth-deficiencies.json'),
  flagged: loadJson('flagged.json'),
};

// ---------------------------------------------------------------------------
// HTML helpers
// ---------------------------------------------------------------------------
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Inline markdown: bold, italic, code, links. Input is raw; escape first.
function inline(s) {
  s = s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return s;
}

function renderMdTable(lines) {
  const rows = lines.map((l) =>
    l.replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
  );
  const body = rows.filter(
    (r) => !(r.length && r.every((c) => /^:?-+:?$/.test(c)))
  );
  const header = body.shift() || [];
  const thead =
    '<thead><tr>' +
    header.map((c) => `<th>${inline(c)}</th>`).join('') +
    '</tr></thead>';
  const tbody =
    '<tbody>' +
    body
      .map(
        (r) =>
          '<tr>' + r.map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>'
      )
      .join('') +
    '</tbody>';
  return `<div class="table-wrap"><table>${thead}${tbody}</table></div>`;
}

function renderMarkdown(md) {
  const lines = md.replace(/\r\n/g, '\n').split('\n');
  const out = [];
  let i = 0;
  let para = [];
  const flushPara = () => {
    if (para.length) {
      out.push('<p>' + inline(para.join(' ')) + '</p>');
      para = [];
    }
  };
  while (i < lines.length) {
    const line = lines[i];

    // Data-table injection token: {{TABLE: key}}
    const token = line.trim().match(/^\{\{TABLE:([a-zA-Z0-9_]+)\}\}$/);
    if (token) {
      flushPara();
      out.push(renderDataTable(token[1]));
      i++;
      continue;
    }

    if (line.trim() === '') {
      flushPara();
      i++;
      continue;
    }

    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      flushPara();
      const lvl = h[1].length;
      out.push(`<h${lvl}>${inline(h[2])}</h${lvl}>`);
      i++;
      continue;
    }

    if (/^(-{3,}|\*{3,})$/.test(line.trim())) {
      flushPara();
      out.push('<hr>');
      i++;
      continue;
    }

    if (/^>\s?/.test(line)) {
      flushPara();
      const q = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        q.push(lines[i].replace(/^>\s?/, ''));
        i++;
      }
      out.push('<blockquote><p>' + inline(q.join(' ')) + '</p></blockquote>');
      continue;
    }

    if (/^\|/.test(line)) {
      flushPara();
      const tbl = [];
      while (i < lines.length && /^\|/.test(lines[i])) {
        tbl.push(lines[i]);
        i++;
      }
      out.push(renderMdTable(tbl));
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      flushPara();
      const items = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*]\s+/, ''));
        i++;
      }
      out.push(
        '<ul>' + items.map((x) => '<li>' + inline(x) + '</li>').join('') + '</ul>'
      );
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      flushPara();
      const items = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s+/, ''));
        i++;
      }
      out.push(
        '<ol>' + items.map((x) => '<li>' + inline(x) + '</li>').join('') + '</ol>'
      );
      continue;
    }

    para.push(line);
    i++;
  }
  flushPara();
  return out.join('\n');
}

// ---------------------------------------------------------------------------
// Source rendering — every data row must carry a resolvable source link.
// ---------------------------------------------------------------------------
function renderSource(src) {
  if (!src) return '<span class="unverified">Unverified</span>';
  const ids = Array.isArray(src) ? src : [src];
  return ids
    .map((id) => {
      const s = sources[id];
      if (!s) {
        return `<span class="unverified" title="Unknown source id: ${escapeHtml(id)}">${escapeHtml(id)}</span>`;
      }
      return `<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">${escapeHtml(s.label)}</a>`;
    })
    .join(' ');
}

function renderDataTable(key) {
  const rows = data[key];
  if (!rows || !rows.length) {
    return '<p class="muted">No table data bound to <code>' + escapeHtml(key) + '</code>.</p>';
  }
  const cols = [];
  for (const r of rows) {
    for (const k of Object.keys(r)) {
      if (k === 'source') continue;
      if (!cols.includes(k)) cols.push(k);
    }
  }
  const head = cols.map((c) => `<th>${escapeHtml(c)}</th>`).join('');
  const body = rows
    .map((r) => {
      const cells = cols
        .map((c) => {
          const v = r[c];
          if (v === '' || v === null || v === undefined) {
            return '<td class="unverified" title="No official source confirmed this value — left blank">—</td>';
          }
          return `<td>${escapeHtml(String(v))}</td>`;
        })
        .join('');
      return `<tr>${cells}<td class="src">${renderSource(r.source)}</td></tr>`;
    })
    .join('');
  return `<div class="table-wrap"><table><thead><tr>${head}<th>Source</th></tr></thead><tbody>${body}</tbody></table></div>`;
}

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------
function navLinks(rel, activeSlug) {
  const cats = {};
  for (const p of PAGES) (cats[p.category] ||= []).push(p);
  let html = '';
  for (const [cat, list] of Object.entries(cats)) {
    html += `<div class="nav-cat"><div class="nav-cat-title">${escapeHtml(cat)}</div>`;
    for (const p of list) {
      const cls = p.slug === activeSlug ? 'nav-link active' : 'nav-link';
      html += `<a class="${cls}" href="${rel}${p.slug}/">${escapeHtml(p.title)}</a>`;
    }
    html += '</div>';
  }
  return html;
}

function layout({ title, activeSlug, content, rel, isLanding }) {
  const nav = navLinks(rel, activeSlug);
  const topLink = isLanding
    ? 'Dashboard'
    : `<a class="back" href="${rel}">← Dashboard</a>`;
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)} · X2 NFL Lines</title>
<link rel="stylesheet" href="${rel}assets/style.css">
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="brand">
      <span class="brand-mark">X2</span>
      <span class="brand-text">NFL Lines</span>
    </div>
    <nav class="nav">${nav}</nav>
    <div class="footer-note">Decision-support system. Verify all values against linked official sources.</div>
  </aside>
  <main class="main">
    <header class="topbar">
      <h1>${escapeHtml(title)}</h1>
      <div class="topbar-right">${topLink}</div>
    </header>
    <div class="content">${content}</div>
  </main>
</div>
</body>
</html>`;
}

// ---------------------------------------------------------------------------
// Landing / dashboard page
// ---------------------------------------------------------------------------
function buildLanding() {
  const counts = {
    requirements: data.requirements?.length || 0,
    questions: data.questions?.length || 0,
    suggestions: data.suggestions?.length || 0,
    strategies: data.strategies?.length || 0,
    gates: data.validationGates?.length || 0,
    flagged: data.flagged?.length || 0,
  };

  const cards = PAGES.map((p) => {
    let n = '';
    if (p.slug === 'requirements') n = counts.requirements;
    else if (p.slug === 'questions-and-answers') n = counts.questions;
    else if (p.slug === 'suggestions') n = counts.suggestions;
    else if (p.slug === 'strategy-research') n = counts.strategies;
    else if (p.slug === 'validation-gates') n = counts.gates;
    else if (p.slug === 'flagged-for-review') n = counts.flagged;
    const badge = n !== '' ? `<span class="card-count">${n}</span>` : '';
    return `<a class="card" href="${p.slug}/">
      <div class="card-cat">${escapeHtml(p.category)}</div>
      <div class="card-title">${escapeHtml(p.title)}${badge}</div>
      <div class="card-desc">${escapeHtml(cardDesc(p.slug))}</div>
    </a>`;
  }).join('\n');

  const content = `
<div class="hero">
  <h2>NFL line generation, strategy validation, and decision support.</h2>
  <p>This site collects, organizes, and analyzes NFL lines and the signals behind them.
  Every table row links to an official source. Values that cannot be confirmed from an
  official source are left blank and flagged as unverified — never inferred.</p>
  <div class="hero-meta">
    <span>Build: <code>npm run build</code></span>
    <span>Verification: <code>npm run verify</code></span>
    <span>Status: ${counts.flagged} flagged items under review</span>
  </div>
</div>
<h2 class="section-title">Navigate</h2>
<div class="card-grid">${cards}</div>
<h2 class="section-title">How to read this site</h2>
<ul class="reading">
  <li><strong>Overview</strong> — executive summary of the project and its key decisions.</li>
  <li><strong>Planning</strong> — the full requirements list, the open questions that must be answered before decisions, and a dedicated Suggestions area for review.</li>
  <li><strong>Strategy</strong> — signal-generation strategies (single bet, parlay, player props), the validation gates each must pass, correlation values, and the leaderboard.</li>
  <li><strong>Data</strong> — injury and depth-chart tracking, the source registry and verification method, and the Flagged-for-Review register.</li>
</ul>
<div class="notice">
  <strong>Verification rule.</strong> No value on this site is inferred. A cell shows
  <span class="unverified">—</span> when no official source confirms it; that item is also listed on the
  <a href="flagged-for-review/">Flagged for Review</a> page with its source link.
</div>`;
  return layout({
    title: 'Dashboard',
    activeSlug: '',
    content,
    rel: '',
    isLanding: true,
  });
}

function cardDesc(slug) {
  const map = {
    'executive-summary': 'Important details and the state of the project at a glance.',
    'requirements': 'The complete list of requirements the system must satisfy.',
    'questions-and-answers': 'Open questions, required information, and current answers.',
    'suggestions:' : 'Proposed improvements, awaiting review before implementation.',
    'suggestions': 'Proposed improvements, awaiting review before implementation.',
    'strategy-research': 'Signal strategies for single bets, parlays, and player props.',
    'validation-gates': 'The gates every strategy must pass to be accepted.',
    'correlation': 'Correlation values used to construct selective combos.',
    'leaderboard': 'Reward structure and ranking for top-performing strategies.',
    'injuries-and-depth': 'Injury tracking and starter/backup depth deficiencies.',
    'data-sources': 'Source registry and the line-by-line verification method.',
    'flagged-for-review': 'Irregularities and unverified items needing review.',
  };
  return map[slug] || '';
}

// ---------------------------------------------------------------------------
// Build
// ---------------------------------------------------------------------------
function build() {
  if (!existsSync(SITE_DIR)) mkdirSync(SITE_DIR, { recursive: true });
  if (!existsSync(ASSETS_DIR)) mkdirSync(ASSETS_DIR, { recursive: true });

  // Landing page
  writeFileSync(join(SITE_DIR, 'index.html'), buildLanding(), 'utf8');

  // Section pages
  for (const p of PAGES) {
    const docPath = join(DOCS_DIR, p.doc);
    const md = readFileSync(docPath, 'utf8');
    const content = renderMarkdown(md);
    const html = layout({
      title: p.title,
      activeSlug: p.slug,
      content,
      rel: '../',
      isLanding: false,
    });
    const dir = join(SITE_DIR, p.slug);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, 'index.html'), html, 'utf8');
  }

  writeFileSync(join(ASSETS_DIR, 'style.css'), STYLE, 'utf8');
  console.log(`[build] Wrote ${PAGES.length + 1} pages to site/.`);
}

const STYLE = readFileSync(join(ROOT, 'src', 'style.css'), 'utf8');

build();
