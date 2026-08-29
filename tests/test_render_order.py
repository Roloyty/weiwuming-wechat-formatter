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

    def test_current_editor_image_syntax_and_preview_copy_are_preserved(self):
        cards = (
            "[universal:https://example.com/poster.jpg|《测试电影》|导演：测试导演，编剧：测试编剧|"
            "上映：2026，片长：101 分钟]\n\n"
            "[origin:https://example.com/art.jpg|作品标题|作者信息|（某某博物馆藏）]\n\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "article.md"
            source.write_text(
                EDITOR_NOTE + BODY + cards + NOTE + AUTHOR + READING + FOOTER,
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    "node",
                    str(RENDERER),
                    str(source),
                    "--editor",
                    str(EDITOR),
                    "--preview",
                ],
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            rendered = source.with_suffix(".html").read_text(encoding="utf-8")
            preview = source.with_name("article.preview.html").read_text(encoding="utf-8")

            self.assertIn('>《测试电影》</strong>', rendered)
            self.assertIn('>作品标题</strong>', rendered)
            self.assertNotIn("**", rendered)
            self.assertIn('class="person-photo origin-photo"', rendered)
            self.assertIn('width: auto; height: auto; max-width: 100%', rendered)
            self.assertIn('class="bracket-note"', rendered)
            self.assertIn('color: #b2b2b2', rendered)
            self.assertIn('id="copyBtn"', preview)
            self.assertIn("ClipboardItem", preview)

    def test_accepts_movie_director_writer_time_and_runtime(self):
        card = (
            "[universal:https://example.com/poster.jpg|《测试电影》|导演：测试导演，编剧：测试编剧|"
            "上映：2026，片长：101 分钟]\n\n"
        )
        result = self.render(EDITOR_NOTE + BODY + card + NOTE + AUTHOR + READING + FOOTER)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_movie_card_without_runtime(self):
        card = (
            "[universal:https://example.com/poster.jpg|《测试电影》|导演：测试导演，编剧：测试编剧|"
            "上映：2026]\n\n"
        )
        result = self.render(EDITOR_NOTE + BODY + card + NOTE + AUTHOR + READING + FOOTER)
        self.assertEqual(result.returncode, 1)
        self.assertIn("片长", result.stderr)

    def test_rejects_movie_synopsis_on_time_line(self):
        card = (
            "[universal:https://example.com/poster.jpg|《测试电影》|导演：测试导演，编剧：测试编剧|"
            "上映：2026，片长：101 分钟；这是未换行的说明]\n\n"
        )
        result = self.render(EDITOR_NOTE + BODY + card + NOTE + AUTHOR + READING + FOOTER)
        self.assertEqual(result.returncode, 1)
        self.assertIn("另起一行", result.stderr)

    def test_rejects_movie_title_with_poster_suffix(self):
        card = (
            "[universal:https://example.com/poster.jpg|《测试电影》海报|导演：测试导演，编剧：测试编剧|"
            "上映：2026，片长：101 分钟]\n\n"
        )
        result = self.render(EDITOR_NOTE + BODY + card + NOTE + AUTHOR + READING + FOOTER)
        self.assertEqual(result.returncode, 1)
        self.assertIn("不要添加“海报”", result.stderr)

    def test_rejects_movie_card_without_screenwriter(self):
        card = (
            "[universal:https://example.com/poster.jpg|《测试电影》|导演：测试导演，主演：测试演员|"
            "上映：2026，片长：101 分钟]\n\n"
        )
        result = self.render(EDITOR_NOTE + BODY + card + NOTE + AUTHOR + READING + FOOTER)
        self.assertEqual(result.returncode, 1)
        self.assertIn("编剧", result.stderr)

    def test_rejects_director_and_screenwriter_on_separate_lines(self):
        card = (
            "[universal:https://example.com/poster.jpg|《测试电影》|导演：测试导演|编剧：测试编剧|"
            "上映：2026，片长：101 分钟]\n\n"
        )
        result = self.render(EDITOR_NOTE + BODY + card + NOTE + AUTHOR + READING + FOOTER)
        self.assertEqual(result.returncode, 1)
        self.assertIn("同一行", result.stderr)


if __name__ == "__main__":
    unittest.main()
