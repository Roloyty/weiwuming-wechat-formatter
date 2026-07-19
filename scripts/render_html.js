#!/usr/bin/env node
/**
 * 谓无名 markdown → 微信粘贴版 HTML 渲染器
 *
 * 不做任何样式移植：直接用 jsdom 加载「编辑器最终版/index.html」，调用编辑器
 * 自己的 preprocessMarkdown → marked.parse → postprocessHtml → applyThemeToPreview
 * → generateInlineStyledHtml 流水线。输出与编辑器「复制」按钮产物逐字节一致，
 * 编辑器 index.html 永远是唯一样式权威——改样式无需同步任何 Python/JS 副本。
 *
 * 用法:
 *   node render_html.js <article.md> [-o article.html] [--preview]
 *                       [--theme-color #8C5237] [--book-color #8C5237]
 *                       [--editor <path/to/index.html>]
 *
 * 编辑器 index.html 查找顺序:
 *   --editor 参数 > 环境变量 WEIWUMING_EDITOR_HTML
 *   > ~/.weiwuming/render.json 的 editor_html 字段
 *   > F:\py\编辑器最终版\index.html（本机默认）
 *   > <skill>/assets/editor-index.html（随 skill 打包的快照，兜底）
 *
 * 输出:
 *   <article>.html          微信粘贴版（inline-styled，body 片段）
 *   <article>.preview.html  --preview 时额外生成，可双击在浏览器验收
 *
 * 退出码: 0 成功 / 1 渲染或校验失败 / 2 输入或编辑器文件缺失
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { JSDOM, VirtualConsole } = require('jsdom');

const SKILL_ROOT = path.dirname(__dirname);

function fail(code, msg) { console.error('✗ ' + msg); process.exit(code); }

// ---------- 参数解析 ----------
const argv = process.argv.slice(2);
let input = null, output = null, preview = false, editorPath = null;
let themeColor = null, bookColor = null;
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '-o') output = argv[++i];
  else if (a === '--preview') preview = true;
  else if (a === '--editor') editorPath = argv[++i];
  else if (a === '--theme-color') themeColor = argv[++i];
  else if (a === '--book-color') bookColor = argv[++i];
  else if (!a.startsWith('-')) input = a;
}
if (!input) fail(2, '用法: node render_html.js <article.md> [-o out.html] [--preview]');
if (!fs.existsSync(input)) fail(2, '找不到输入文件: ' + input);
if (!output) output = input.replace(/\.md$/i, '') + '.html';

// ---------- 定位编辑器 index.html ----------
function resolveEditor() {
  const candidates = [];
  if (editorPath) candidates.push(editorPath);
  if (process.env.WEIWUMING_EDITOR_HTML) candidates.push(process.env.WEIWUMING_EDITOR_HTML);
  const cfgFile = path.join(os.homedir(), '.weiwuming', 'render.json');
  if (fs.existsSync(cfgFile)) {
    try {
      const c = JSON.parse(fs.readFileSync(cfgFile, 'utf8'));
      if (c.editor_html) candidates.push(c.editor_html);
    } catch (e) { /* 配置损坏则忽略 */ }
  }
  candidates.push('F:\\py\\编辑器最终版\\index.html');
  candidates.push(path.join(SKILL_ROOT, 'assets', 'editor-index.html'));
  for (const c of candidates) if (c && fs.existsSync(c)) return c;
  fail(2, '找不到编辑器 index.html，候选: ' + candidates.join(' | '));
}
const editorFile = resolveEditor();

// ---------- 组装 jsdom 环境（marked CDN → 本地内联） ----------
let html = fs.readFileSync(editorFile, 'utf8');
const markedSrc = fs.readFileSync(
  path.join(SKILL_ROOT, 'node_modules', 'marked', 'lib', 'marked.umd.js'), 'utf8');
const cdnRe = /<script\s+src="https:\/\/cdn\.jsdelivr\.net\/npm\/marked\/marked\.min\.js"><\/script>/;
if (!cdnRe.test(html)) fail(1, '编辑器 HTML 里没找到 marked CDN 标签，无法注入本地 marked（编辑器结构变了？）');
html = html.replace(cdnRe, () => '<script>' + markedSrc + '\n</script>');

const vc = new VirtualConsole();  // 收集页面脚本报错，避免静默失败
const pageErrors = [];
vc.on('jsdomError', e => pageErrors.push(e.message || String(e)));
vc.on('error', (...a) => pageErrors.push(a.map(String).join(' ')));

const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  url: 'file:///' + editorFile.replace(/\\/g, '/'),
  virtualConsole: vc,
});
const { window } = dom;
const { document } = window;

// jsdom 没有的 API 补桩（编辑器加载时可能引用）
if (!window.matchMedia) window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });

for (const fn of ['preprocessMarkdown', 'postprocessHtml', 'applyThemeToPreview', 'generateInlineStyledHtml']) {
  if (typeof window[fn] !== 'function') {
    fail(1, `编辑器里找不到 ${fn}()，index.html 结构可能已变化。页面报错: ${pageErrors.join('; ') || '无'}`);
  }
}

// ---------- 渲染（复刻 updatePreview + copyRichText 的路径） ----------
const md = fs.readFileSync(input, 'utf8');
const previewEl = document.getElementById('preview');
if (!previewEl) fail(1, '编辑器页面里没有 #preview 元素');

if (themeColor) window.currentThemeColor = themeColor;
if (bookColor) {
  window.currentBookColor = bookColor;
  window.currentBookColorLight = window.computeLighterColor
    ? window.computeLighterColor(bookColor) : bookColor;
}

let styled;
try {
  const processed = window.preprocessMarkdown(md);
  let bodyHtml = window.marked.parse(processed);
  bodyHtml = window.postprocessHtml(bodyHtml);
  previewEl.innerHTML = bodyHtml;
  window.applyThemeToPreview(previewEl, window.currentThemeColor);
  styled = window.generateInlineStyledHtml(previewEl);
} catch (e) {
  fail(1, '渲染失败: ' + (e.stack || e));
}
if (!styled || !styled.trim()) fail(1, '渲染结果为空');

// ---------- 稳定性校验 ----------
const problems = [];
const outDom = new JSDOM('<body>' + styled + '</body>');
const odoc = outDom.window.document;

// 1. 所有 <img> 必须是 http(s) 公网地址（本地路径粘进公众号必裂图）。
//    编辑器自带的 data:SVG 空封面占位图放行；空 src（图片字段留空）只警告。
const warnings = [];
const imgs = [...odoc.querySelectorAll('img')];
for (const img of imgs) {
  const src = img.getAttribute('src') || '';
  if (src === '') warnings.push('有卡片图片字段为空（微信里会显示裂图图标，建议补图或在校对提醒中说明）');
  else if (src.startsWith('data:')) { /* 编辑器空封面占位，合法 */ }
  else if (!/^https?:\/\//.test(src)) problems.push(`非公网图片 src="${src.slice(0, 80)}"（本地路径粘进公众号必裂图，先跑 upload_image.py）`);
}
// 2. 源文件里的成对语法必须真的渲染出来（防止语法笔误静默丢块）
const pairChecks = [
  [/^>>> /m, '.editor-note', '编者按 >>> <<<'],
  [/^---\[dot\]/m, '.divider-dot', '小标题装饰 ---[dot]'],
  [/^---\[notes\]/m, '.notes-section, .end-notes', '注释块 ---[notes]'],
  [/^---\[bio-title:/m, '.bio-title', '简介块 ---[bio-title:]'],
  [/^---\[reading-title:/m, '.reading-title', '延伸阅读块 ---[reading-title:]'],
  [/^---\[follow\]/m, '.follow-section, .follow-line', '关注引导 ---[follow]'],
  [/^\[book:/m, '.book-title', '[book:] 书籍卡片'],
  [/^\[universal:/m, '.person-name, .person-info', '[universal:] 人物卡片'],
  [/^\[reading-book:/m, '.reading-book-title, .reading-item', '[reading-book:] 条目'],
  [/^\[staff:/m, null, '[staff:] 条目'],
];
for (const [mdRe, sel, label] of pairChecks) {
  if (mdRe.test(md) && sel && !odoc.querySelector(sel)) {
    problems.push(`源文件含 ${label}，但渲染结果中未找到对应元素（检查语法是否规范）`);
  }
}
// 3. 未被识别的语法残渣：渲染产物纯文本里不应再出现语法标记
const plain = odoc.body.textContent || '';
for (const leak of ['---[', '[book:', '[enbook:', '[jpbook:', '[universal:', '[reading-book:', '[staff:', '[bio:', '<<<']) {
  if (plain.includes(leak)) problems.push(`语法残渣未被解析: "${leak}"（多为标记拼写/空格问题）`);
}
if (/^>>>[^ ]/m.test(md)) problems.push('">>>" 后缺空格，编者按不会被识别');

// ---------- 写文件 ----------
fs.writeFileSync(output, styled, 'utf8');
let previewFile = null;
if (preview) {
  previewFile = output.replace(/\.html$/i, '') + '.preview.html';
  fs.writeFileSync(previewFile,
    `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>预览 - ${path.basename(input)}</title>
<style>body{margin:0;background:#e5e5e5}#wx{width:414px;margin:20px auto;background:#fff;padding:20px 16px;box-shadow:0 2px 12px rgba(0,0,0,.15)}</style>
</head><body><div id="wx">${styled}</div></body></html>`, 'utf8');
}

// ---------- 报告 ----------
console.log(`✓ 渲染完成: ${output}`);
if (previewFile) console.log(`✓ 浏览器预览: ${previewFile}`);
console.log(`  编辑器: ${editorFile}`);
console.log(`  统计: ${(plain.replace(/\s/g, '').length)} 字 | ${imgs.length} 张图 | ${odoc.querySelectorAll('section').length} 个 section`);
for (const w of warnings) console.log('⚠ ' + w);
if (problems.length) {
  console.error('✗ 校验未通过:');
  for (const p of problems) console.error('  - ' + p);
  process.exit(1);
}
console.log('✓ 校验通过（图片全公网 / 语法块全渲染 / 无语法残渣）');
