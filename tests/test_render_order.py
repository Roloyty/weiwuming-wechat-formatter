from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts" / "render_html.js"
EDITOR = ROOT / "assets" / "editor-index.html"

EDITOR_NOTE = ">>> 编者按：这是用于验证结构顺序的测试内容。\n<<<\n\n"
BODY = "正文内容。\n\n"
NOTE = "---[note]\n\n- 测试来源。\n\n---[/note]\n\n"
AUTHOR = "---[bio-title:作者简介]\n\n[bio:测试作者。]\n\n---[/bio]\n\n"
READING = (
    "---[reading-title:延伸阅读]\n\n"
    "[reading-book:测试书|测试作者||]\n\n"
    "---[/reading]\n\n"
)
FOOTER = (
    "[staff:测试作者|编辑]\n\n"
    "[staff:春生、|审校]\n\n"
    "---[follow]\n\n东亚视角 全球视野\n\n---[/follow]\n"
)


class RenderOrderTests(unittest.TestCase):
    def render(self, markdown: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "article.md"
            source.write_text(markdown, encoding="utf-8")
            return subprocess.run(
                ["node", str(RENDERER), str(source), "--editor", str(EDITOR)],
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )

    def test_accepts_strict_article_order(self):
        result = self.render(EDITOR_NOTE + BODY + NOTE + AUTHOR + READING + FOOTER)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_title_above_editor_note(self):
        result = self.render("### 文章标题\n\n" + EDITOR_NOTE + BODY + NOTE + AUTHOR + READING + FOOTER)
        self.assertEqual(result.returncode, 1)
        self.assertIn("首个非空内容", result.stderr)

    def test_rejects_author_before_source_note(self):
        result = self.render(EDITOR_NOTE + BODY + AUTHOR + NOTE + READING + FOOTER)
        self.assertEqual(result.returncode, 1)
        self.assertIn("顺序错误", result.stderr)


if __name__ == "__main__":
    unittest.main()
