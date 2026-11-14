// src/verify.mjs — verify the generated site and the data tables.
// 1) Every data-table row must reference a source id that resolves in sources.json.
// 2) Every internal link in the generated site must resolve to an existing file.
// Exits non-zero on any failure.

import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const DATA_DIR = join(ROOT, 'data');
const SITE_DIR = join(ROOT, 'site');

let errors = 0;
const log = (ok, msg) => {
  if (!ok) errors++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${msg}`);
};

// --- 1. Source resolution for every data row ---
const sources = JSON.parse(readFileSync(join(DATA_DIR, 'sources.json'), 'utf8'));

const DATA_KEYS = [
  'requirements', 'questions', 'suggestions', 'strategies',
  'validation-gates', 'correlations', 'leaderboard', 'injuries',
  'depth-deficiencies', 'flagged',
];

console.log('\n[1] Data-table source resolution');
for (const key of DATA_KEYS) {
  const file = join(DATA_DIR, `${key}.json`);
  if (!existsSync(file)) {
    log(false, `${key}: data file missing`);
    continue;
  }
  const rows = JSON.parse(readFileSync(file, 'utf8'));
  let rowOk = true;
  for (const r of rows) {
    const src = r.source;
    if (!src) {
      rowOk = false;
      log(false, `${key} row ${r.id ?? '?'}: no source`);
      continue;
    }
    const ids = Array.isArray(src) ? src : [src];
    for (const id of ids) {
      if (!sources[id]) {
        rowOk = false;
        log(false, `${key} row ${r.id ?? '?'}: unknown source id "${id}"`);
      }
    }
  }
  if (rowOk) log(true, `${key}: ${rows.length} rows, all sources resolve`);
}

// --- 2. Internal link resolution in the generated site ---
console.log('\n[2] Internal link resolution');
if (!existsSync(SITE_DIR)) {
  log(false, 'site/ directory does not exist — run `npm run build` first');
  process.exit(1);
}

function listHtml(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) out.push(...listHtml(p));
    else if (entry.endsWith('.html')) out.push(p);
  }
  return out;
}

const htmlFiles = listHtml(SITE_DIR);
let linkChecks = 0;
for (const file of htmlFiles) {
  const html = readFileSync(file, 'utf8');
  const dir = dirname(file);
  const links = [...html.matchAll(/href="([^"]+)"/g)].map((m) => m[1]);
  for (const href of links) {
    if (/^(https?:|mailto:|#)/.test(href)) continue; // external or anchor
    // strip fragment
    const path = href.split('#')[0];
    if (!path) continue;
    const target = resolve(dir, path);
    linkChecks++;
    if (!existsSync(target)) {
      log(false, `${file}: broken link -> ${href}`);
    }
  }
}
log(true, `checked ${linkChecks} internal links across ${htmlFiles.length} HTML files`);

console.log(`\n[verify] ${errors === 0 ? 'ALL CHECKS PASSED' : `${errors} FAILURE(S)`}`);
process.exit(errors === 0 ? 0 : 1);
