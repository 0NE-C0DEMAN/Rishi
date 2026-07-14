/* Build ui/dashboard.html from ui/dashboard.src.html.
 *
 * dashboard.src.html authors the React app in JSX (readable source). This
 * precompiles the JSX and inlines React so the shipped ui/dashboard.html is a
 * single self-contained file with no runtime Babel and no React CDN fetch —
 * faster and more reliable inside the Streamlit components.html iframe.
 *
 * Setup (once):   cd scripts && npm i react@18 react-dom@18 @babel/standalone
 * Build:          node scripts/build_dashboard.mjs
 *
 * The __PAYLOAD__ / __GEMINI_KEY__ placeholders are preserved; ui/bundle.py
 * fills them at request time.
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import babel from '@babel/standalone';

const here = path.dirname(fileURLToPath(import.meta.url));
const UI = path.resolve(here, '..', 'ui');
const NM = path.resolve(here, 'node_modules');

const src = fs.readFileSync(path.join(UI, 'dashboard.src.html'), 'utf8');
const m = src.match(/<script type="text\/babel"[^>]*>([\s\S]*?)<\/script>/);
if (!m) { console.error('no text/babel script found in dashboard.src.html'); process.exit(1); }

let code;
try {
  code = babel.transform(m[1], { presets: ['react'], compact: false }).code;
} catch (e) {
  console.error('BABEL ERROR:\n' + e.message);
  process.exit(1);
}

const react = fs.readFileSync(path.join(NM, 'react/umd/react.production.min.js'), 'utf8');
const reactDom = fs.readFileSync(path.join(NM, 'react-dom/umd/react-dom.production.min.js'), 'utf8');

// Function replacers so `$` sequences in minified React aren't interpreted as
// special String.replace patterns.
let html = src;
html = html.replace(/<script crossorigin src="https:\/\/unpkg\.com\/react@18\/[^"]*"><\/script>/, () => `<script>${react}</script>`);
html = html.replace(/<script crossorigin src="https:\/\/unpkg\.com\/react-dom@18\/[^"]*"><\/script>/, () => `<script>${reactDom}</script>`);
html = html.replace(/\s*<script src="https:\/\/unpkg\.com\/@babel\/standalone\/[^"]*"><\/script>/, () => '');
html = html.replace(/<script type="text\/babel"[^>]*>[\s\S]*?<\/script>/, () => `<script>${code}</script>`);

fs.writeFileSync(path.join(UI, 'dashboard.html'), html);
console.log('built ui/dashboard.html:', html.length, 'chars | compiled JS:', code.length, 'chars');
