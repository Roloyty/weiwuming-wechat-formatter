#!/usr/bin/env node
/**
 * 从本仓库生成一份干净的 skill 发布包。
 *
 * 解决两件事：
 *   1. 根 index.html 与 assets/editor-index.html 是同一份编辑器的两个位置
 *      （前者配 vendor/marked.min.js 可直接双击打开，后者是 render_html.js 的
 *      兜底快照）。历史上它们靠手工同步，会漂移。这里以根 index.html 为准
 *      单向覆盖 assets/editor-index.html。
 *   2. 过去靠往目标目录里"复制文件"来安装 skill，复制出来的副本各自漂移。
 *      发布包由本脚本生成，仓库是唯一事实来源。
 *
 * 用法:
 *   node scripts/build_skill_package.js            # 同步 + 打包到 dist/skill
 *   node scripts/build_skill_package.js --check    # 只校验同步状态，不写文件
 *   node scripts/build_skill_package.js -o <dir>   # 指定输出目录
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

// 发布包内容：只放 skill 运行时真正需要的东西
const INCLUDE = [
  'SKILL.md',
  'README.md',
  '使用文档.md',
  'package.json',
  'favicon.svg',
  'index.html',
  'assets',
  'references',
  'scripts',
  'vendor',
];

// 即使在 INCLUDE 的目录里也要跳过
const SKIP = new Set(['node_modules', '__pycache__', '.git', 'outputs', 'images', 'dist']);
const SKIP_EXT = new Set(['.pyc']);

const argv = process.argv.slice(2);
const checkOnly = argv.includes('--check');
const outIdx = argv.findIndex((a) => a === '-o' || a === '--out');
const OUT = outIdx >= 0 && argv[outIdx + 1]
  ? path.resolve(argv[outIdx + 1])
  : path.join(ROOT, 'dist', 'skill');

function fail(msg) {
  console.error('✗ ' + msg);
  process.exit(1);
}

// ---------- 1. 编辑器副本同步 ----------
const editorSrc = path.join(ROOT, 'index.html');
const editorDst = path.join(ROOT, 'assets', 'editor-index.html');

if (!fs.existsSync(editorSrc)) fail('找不到根 index.html');

const srcBuf = fs.readFileSync(editorSrc);
const dstBuf = fs.existsSync(editorDst) ? fs.readFileSync(editorDst) : null;
const inSync = dstBuf !== null && srcBuf.equals(dstBuf);

if (inSync) {
  console.log('✓ 编辑器副本已同步 (index.html == assets/editor-index.html)');
} else if (checkOnly) {
  fail('编辑器副本不同步：assets/editor-index.html 与根 index.html 不一致。'
    + '\n  跑 `node scripts/build_skill_package.js` 以根 index.html 为准覆盖它。');
} else {
  fs.mkdirSync(path.dirname(editorDst), { recursive: true });
  fs.writeFileSync(editorDst, srcBuf);
  console.log('✓ 已同步 assets/editor-index.html ← index.html');
}

// ---------- 2. SKILL.md frontmatter 自检 ----------
const skillMd = fs.readFileSync(path.join(ROOT, 'SKILL.md'), 'utf8');
const fm = skillMd.match(/^---\r?\n([\s\S]*?)\r?\n---/);
if (!fm) fail('SKILL.md 缺少 frontmatter');
for (const key of ['name', 'description']) {
  if (!new RegExp('^' + key + ':', 'm').test(fm[1])) {
    fail(`SKILL.md frontmatter 缺少 \`${key}:\`（Claude Code 靠它发现 skill）`);
  }
}
console.log('✓ SKILL.md frontmatter 含 name / description');

if (checkOnly) {
  console.log('\n检查通过。');
  process.exit(0);
}

// ---------- 3. 生成发布包 ----------
function copyInto(src, dst) {
  const st = fs.statSync(src);
  if (st.isDirectory()) {
    if (SKIP.has(path.basename(src))) return 0;
    fs.mkdirSync(dst, { recursive: true });
    let n = 0;
    for (const entry of fs.readdirSync(src)) {
      n += copyInto(path.join(src, entry), path.join(dst, entry));
    }
    return n;
  }
  if (SKIP_EXT.has(path.extname(src))) return 0;
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
  return 1;
}

fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT, { recursive: true });

let count = 0;
const missing = [];
for (const item of INCLUDE) {
  const src = path.join(ROOT, item);
  if (!fs.existsSync(src)) { missing.push(item); continue; }
  count += copyInto(src, path.join(OUT, item));
}

const version = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8')).version;
console.log(`✓ 发布包已生成: ${OUT}`);
console.log(`  版本 ${version}，共 ${count} 个文件`);
if (missing.length) console.log('  (跳过不存在的条目: ' + missing.join(', ') + ')');
console.log('\n注意：本机 skill 已通过 junction 直接指向仓库');
console.log('      %USERPROFILE%\\.claude\\skills\\wechat-formatter -> ' + ROOT);
console.log('      改仓库即生效，无需安装此发布包；发布包只用于分发给别人。');
