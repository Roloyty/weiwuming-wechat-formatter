const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const root = path.resolve(__dirname, '..');
const marked = fs.readFileSync(path.join(path.dirname(require.resolve('marked')), 'marked.umd.js'), 'utf8');
const titles = [
    'The Political Philosophy of Zhang Taiyan: The Resistance of Consciousness',
    'The Politics of Time in China and Japan: Back to the Future',
    'Pan-Asianism and the Legacy of the Chinese Revolution',
    'Confronting Capital and Empire: Rethinking Kyoto School Philosophy',
];
const bio = `慕唯仁（Viren Murthy），美国威斯康星大学麦迪逊分校历史系教授，研究中国、日本与印度思想史，关注亚洲思想家对现代性与全球资本主义的抵抗。著有 *${titles[0]}*（2011）、*${titles[1]}*（2022）、*${titles[2]}*（2023），并与 Max Ward、Fabian Schäfer 合编 *${titles[3]}*（2017）。`;
const md = `---[bio-title:作者简介]\n[bio:${bio}]\n---[/bio]\n\n---[bio-title:译者简介]\n[bio:普通文字，**粗体**，***粗斜体***。]\n---[/bio]`;
const editors = process.argv.slice(2);
if (!editors.length) editors.push(path.join(root, 'index.html'), path.join(root, 'assets/editor-index.html'));
for (const editor of editors) {
    const html = fs.readFileSync(editor, 'utf8').replace(/<script\b[^>]*\bsrc=(["'])[^"']*marked(?:\.min)?\.js(?:\?[^"']*)?\1[^>]*>\s*<\/script>/i, () => `<script>${marked}</script>`);
    const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true });
    try {
        const w = dom.window;
        const preview = w.document.getElementById('preview');
        preview.innerHTML = w.postprocessHtml(w.marked.parse(w.preprocessMarkdown(md)));
        w.applyThemeToPreview(preview, w.currentThemeColor);
        for (const [stage, container] of [
            ['preview', preview],
            ['copy', new JSDOM(w.generateInlineStyledHtml(preview)).window.document],
        ]) {
            const bios = container.querySelectorAll('.bio-text');
            assert.equal(bios.length, 2, stage);
            assert.deepEqual(Array.from(bios[0].querySelectorAll('em'), el => el.textContent), titles, stage);
            assert.equal(bios[0].textContent, bio.replaceAll('*', ''), stage);
            assert.equal(bios[1].querySelector('strong').textContent, '粗体', stage);
            assert.equal(bios[1].querySelector('strong em').textContent, '粗斜体', stage);
            for (const paragraph of bios) assert.ok(!paragraph.textContent.includes('*'), stage);
            if (stage === 'copy') {
                for (const em of bios[0].querySelectorAll('em')) assert.equal(em.style.fontStyle, 'italic');
            }
        }
        console.log(`PASS bio preview and copy: ${editor}`);
    } finally { dom.window.close(); }
}
