#!/usr/bin/env node
/**
 * 谓无名 markdown → 微信粘贴版 HTML 渲染器
 *
 * 不做任何样式移植：直接用 jsdom 加载网页版 index.html，调用编辑器
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
 *   > F:\py\tools.weiwuming.cn\index.html（本机网页版，优先）
 *   > <skill>/assets/editor-index.html（随 skill 打包的快照，兜底）
 *   > F:\py\编辑器最终版\index.html（旧路径，仅兼容）
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
  candidates.push('F:\\py\\tools.weiwuming.cn\\index.html');
  candidates.push(path.join(SKILL_ROOT, 'assets', 'editor-index.html'));
  candidates.push('F:\\py\\编辑器最终版\\index.html');
  for (const c of candidates) if (c && fs.existsSync(c)) return c;
  fail(2, '找不到编辑器 index.html，候选: ' + candidates.join(' | '));
}
const editorFile = resolveEditor();

// ---------- 组装 jsdom 环境（网页版的 marked 脚本 → npm 依赖内联） ----------
let html = fs.readFileSync(editorFile, 'utf8');
const markedEntry = require.resolve('marked');
const markedSrc = fs.readFileSync(
  path.join(path.dirname(markedEntry), 'marked.umd.js'), 'utf8');
const markedScriptRe = /<script\b[^>]*\bsrc=(["'])[^"']*marked(?:\.min)?\.js(?:\?[^"']*)?\1[^>]*>\s*<\/script>/i;
if (!markedScriptRe.test(html)) {
  fail(1, '编辑器 HTML 里没找到 marked 脚本标签，无法注入 npm 版 marked（编辑器结构变了？）');
}
html = html.replace(markedScriptRe, () => '<script>' + markedSrc + '\n</script>');

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

// 0. 文章结构必须严格遵循发布顺序；编者按必须是首个非空内容，前面不放文章标题。
const normalizedMd = md.replace(/^\uFEFF/, '');
const firstNonEmptyLine = normalizedMd.split(/\r?\n/).find(line => line.trim() !== '') || '';
if (!firstNonEmptyLine.startsWith('>>> ')) {
  problems.push('文章首个非空内容必须是“>>> 编者按…”，编者按上方不要放文章标题或其他内容');
}

function markerIndex(re) {
  const match = re.exec(normalizedMd);
  return match ? match.index : -1;
}

const structure = {
  editorStart: markerIndex(/^>>> /m),
  editorEnd: markerIndex(/^<<<\s*$/m),
  toc: markerIndex(/^---\[toc\]\s*$/m),
  notes: markerIndex(/^---\[notes\]\s*$/m),
  note: markerIndex(/^---\[note\]\s*$/m),
  author: markerIndex(/^---\[bio-title:作者简介\]\s*$/m),
  translator: markerIndex(/^---\[bio-title:译者简介\]\s*$/m),
  reading: markerIndex(/^---\[reading-title:延伸阅读\]\s*$/m),
  staff: markerIndex(/^\[staff:/m),
  follow: markerIndex(/^---\[follow\]\s*$/m),
};

for (const [key, label] of [
  ['editorStart', '编者按'],
  ['editorEnd', '编者按结束标记 <<<'],
  ['note', '来源说明 ---[note]'],
  ['author', '作者简介'],
  ['reading', '延伸阅读'],
  ['staff', 'staff 署名'],
  ['follow', '关注引导'],
]) {
  if (structure[key] < 0) problems.push(`缺少必需模块：${label}`);
}

const orderedMarkers = [
  ['editorStart', '编者按'],
  ['editorEnd', '编者按结束'],
  ['toc', '目录'],
  ['notes', '注释'],
  ['note', '来源说明'],
  ['author', '作者简介'],
  ['translator', '译者简介'],
  ['reading', '延伸阅读'],
  ['staff', 'staff 署名'],
  ['follow', '关注引导'],
].filter(([key]) => structure[key] >= 0);
for (let i = 1; i < orderedMarkers.length; i++) {
  const [prevKey, prevLabel] = orderedMarkers[i - 1];
  const [key, label] = orderedMarkers[i];
  if (structure[key] <= structure[prevKey]) {
    problems.push(`文章模块顺序错误：“${label}”必须位于“${prevLabel}”之后`);
  }
}

if (structure.editorEnd >= 0) {
  const bodyEnds = [structure.toc, structure.notes, structure.note].filter(index => index > structure.editorEnd);
  const bodyEnd = bodyEnds.length ? Math.min(...bodyEnds) : normalizedMd.length;
  if (!normalizedMd.slice(structure.editorEnd + 3, bodyEnd).trim()) {
    problems.push('编者按之后、目录/注释/来源说明之前必须有正文');
  }
}

const bioMarkers = [...normalizedMd.matchAll(/^---\[bio-title:[^\]]+\]\s*$/gm)];
if (bioMarkers.length && structure.author >= 0 && bioMarkers[0].index !== structure.author) {
  problems.push('作者简介必须是来源说明之后的第一个简介模块');
}
for (const bio of bioMarkers) {
  if (structure.note >= 0 && bio.index <= structure.note) problems.push('简介模块必须位于 ---[note] 之后');
  if (structure.reading >= 0 && bio.index >= structure.reading) problems.push('简介模块必须位于延伸阅读之前');
}

const staffMarkers = [...normalizedMd.matchAll(/^\[staff:[^\]]+\]\s*$/gm)];
if (staffMarkers.length !== 2) problems.push(`必须有且只有两条 [staff:]，当前为 ${staffMarkers.length} 条`);
if (staffMarkers.length && structure.follow >= 0 && staffMarkers.at(-1).index >= structure.follow) {
  problems.push('所有 [staff:] 必须位于关注引导 ---[follow] 之前');
}

// 电影/电视剧卡片：标题不加“海报”，导演+编剧同一行，时间+片长同一行。
const universalLines = normalizedMd.match(/^\[universal:[^\r\n]+\]\s*$/gm) || [];
for (const line of universalLines) {
  const fields = line.trim().slice('[universal:'.length, -1).split('|').map(field => field.trim());
  const title = fields[1] || '';
  const timeIndex = fields.findIndex(field => /^(上映|首播)：/.test(field));
  const isMovieOrTv = title.includes('海报') || timeIndex >= 0;
  if (!isMovieOrTv) continue;
  if (title.includes('海报')) {
    problems.push(`电影/电视剧卡片标题“${title}”只写作品名，不要添加“海报”二字`);
  }
  if (timeIndex < 0) {
    problems.push(`电影/电视剧卡片“${title}”缺少“上映/首播 + 片长”时间行`);
    continue;
  }
  const creditsField = fields[2] || '';
  const creditsMatch = creditsField.match(/^导演：(.+)，编剧：(.+)$/);
  if (!creditsMatch) {
    problems.push(`电影/电视剧卡片“${title}”必须在同一字段填写“导演：姓名，编剧：姓名”，使导演和编剧显示在同一行；不要用主演/配音替代编剧`);
  } else if (/[、，]/.test(creditsMatch[1]) || /[、，]/.test(creditsMatch[2])) {
    problems.push(`电影/电视剧卡片“${title}”的多位导演或编剧请用“/”分隔`);
  }
  const timeField = fields[timeIndex];
  if (timeField.startsWith('上映：') && !/^上映：.+，片长：.+(?:分钟|小时)$/.test(timeField)) {
    problems.push(`电影卡片“${title}”的时间行必须为“上映：年份，片长：时长”，说明请用后续 | 字段另起一行`);
  }
  if (timeField.startsWith('首播：') && !/^首播：.+，(?:单集)?片长：.+(?:分钟|小时|集)$/.test(timeField)) {
    problems.push(`电视剧卡片“${title}”的时间行必须包含“首播”和“片长”，说明请用后续 | 字段另起一行`);
  }
}

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
  [/^---\[toc\]/m, '.toc-title, .toc-scroll', '目录块 ---[toc]'],
  [/^---\[notes\]/m, '.notes-section, .end-notes', '注释块 ---[notes]'],
  [/^---\[note\]/m, '.end-notes', '来源说明 ---[note]'],
  [/^---\[bio-title:/m, '.bio-title', '简介块 ---[bio-title:]'],
  [/^\[bio-img:/m, '.bio-img img', '[bio-img:] 简介图片'],
  [/^---\[reading-title:/m, '.reading-title', '延伸阅读块 ---[reading-title:]'],
  [/^---\[follow\]/m, '.follow-section, .follow-line', '关注引导 ---[follow]'],
  [/^\[book:/m, '.book-title', '[book:] 书籍卡片'],
  [/^\[enbook:/m, '.enbook-title', '[enbook:] 英文书籍卡片'],
  [/^\[jpbook:/m, '.jpbook-title', '[jpbook:] 日文书籍卡片'],
  [/^\[universal:/m, '.person-name, .person-info', '[universal:] 人物卡片'],
  [/^\[origin:/m, '.origin-info .origin-photo img', '[origin:] 原图尺寸图片卡片'],
  [/^\[reading-book:/m, '.reading-book-title, .reading-item', '[reading-book:] 条目'],
  [/^\[reading-enbook:/m, '.reading-enbook-title', '[reading-enbook:] 条目'],
  [/^\[reading-jpbook:/m, '.reading-jpbook-title', '[reading-jpbook:] 条目'],
  [/^\[staff:/m, null, '[staff:] 条目'],
];
for (const [mdRe, sel, label] of pairChecks) {
  if (mdRe.test(md) && sel && !odoc.querySelector(sel)) {
    problems.push(`源文件含 ${label}，但渲染结果中未找到对应元素（检查语法是否规范）`);
  }
}
// 3. 未被识别的语法残渣：渲染产物纯文本里不应再出现语法标记
const plain = odoc.body.textContent || '';
for (const leak of ['---[', '[book:', '[enbook:', '[jpbook:', '[universal:', '[origin:', '[reading-book:', '[reading-enbook:', '[reading-jpbook:', '[staff:', '[bio:', '[bio-img:', '<<<']) {
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
<style>
body{margin:0;background:#e5e5e5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
#toolbar{position:sticky;top:0;z-index:10;display:flex;align-items:center;justify-content:center;gap:12px;padding:12px;background:#20262e;color:#fff;box-shadow:0 2px 8px rgba(0,0,0,.2)}
#copyBtn{border:0;border-radius:999px;padding:8px 18px;background:#3daad6;color:#fff;font-size:14px;font-weight:600;cursor:pointer}
#copyBtn:active{transform:translateY(1px)}#copyStatus{font-size:13px;color:#d8dee6}
#wx{width:414px;box-sizing:border-box;margin:20px auto;background:#fff;padding:20px 16px;box-shadow:0 2px 12px rgba(0,0,0,.15)}
</style>
</head><body><div id="toolbar"><button id="copyBtn" type="button">复制排版结果</button><span id="copyStatus">复制后直接粘贴到微信公众号编辑器</span></div><div id="wx">${styled}</div>
<script>
(function(){
  var button=document.getElementById('copyBtn');
  var status=document.getElementById('copyStatus');
  var content=document.getElementById('wx');
  function fallbackCopy(){
    var selection=window.getSelection();
    var range=document.createRange();
    range.selectNodeContents(content);selection.removeAllRanges();selection.addRange(range);
    var ok=document.execCommand('copy');selection.removeAllRanges();
    if(!ok)throw new Error('execCommand copy failed');
  }
  button.addEventListener('click',async function(){
    try{
      var rich=content.innerHTML;var plain=content.innerText;
      if(navigator.clipboard&&window.ClipboardItem){
        var item=new ClipboardItem({'text/html':new Blob([rich],{type:'text/html'}),'text/plain':new Blob([plain],{type:'text/plain'})});
        await navigator.clipboard.write([item]);
      }else{fallbackCopy()}
      status.textContent='已复制，可直接粘贴到微信公众号编辑器';
    }catch(error){
      try{fallbackCopy();status.textContent='已复制，可直接粘贴到微信公众号编辑器'}
      catch(fallbackError){status.textContent='复制失败，请在页面内全选文章后复制'}
    }
  });
})();
</script></body></html>`, 'utf8');
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
console.log('✓ 校验通过（编者按首位 / 模块顺序 / 图片全公网 / 语法块全渲染 / 无语法残渣）');
