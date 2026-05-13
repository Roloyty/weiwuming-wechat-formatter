#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import importlib.util
import re
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
EXTRACTOR = SCRIPT_DIR / "extract_docx.py"
ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)


def load_extractor():
    spec = importlib.util.spec_from_file_location("extract_docx", EXTRACTOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load extractor: {EXTRACTOR}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def extract_run_text_with_notes(run):
        chunks: list[str] = []
        for child in list(run):
            if child.tag == mod.qn("w:t"):
                chunks.append(child.text or "")
            elif child.tag == mod.qn("w:tab"):
                chunks.append("\t")
            elif child.tag in {mod.qn("w:br"), mod.qn("w:cr")}:
                chunks.append("\n")
            elif child.tag == mod.qn("w:noBreakHyphen"):
                chunks.append("-")
            elif child.tag == mod.qn("w:footnoteReference"):
                note_id = child.attrib.get(mod.qn("w:id"), "")
                chunks.append("^" + note_mark(note_id))
        return "".join(chunks)

    mod.extract_run_text = extract_run_text_with_notes
    return mod


def note_mark(note_id: str) -> str:
    if note_id.isdigit():
        n = int(note_id)
        if 1 <= n <= 20:
            return chr(0x2460 + n - 1)
    return f"[{note_id}]"


def clean_text(value: str) -> str:
    return value.translate(ZERO_WIDTH).strip()


def is_empty(item: dict) -> bool:
    return not clean_text(item.get("text", ""))


def is_section_heading(text: str) -> bool:
    cn_nums = "\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341"
    return bool(re.match(rf"^[{cn_nums}]+[、.]", text)) and len(text) <= 24


def first_non_empty(items: list[dict], start: int = 0) -> tuple[int, dict] | tuple[None, None]:
    for i in range(start, len(items)):
        if not is_empty(items[i]):
            return i, items[i]
    return None, None


def find_duplicate_title(items: list[dict], title: str, start: int) -> int | None:
    for i in range(start, len(items)):
        if clean_text(items[i].get("text", "")) == title:
            return i
    return None


def extract_author(author_info: str) -> str:
    if not author_info:
        return ""
    parts = [p for p in re.split(r"\s+", author_info) if p]
    phone_label = "\u8054\u7cfb\u7535\u8bdd"
    for idx, part in enumerate(parts):
        if part.startswith(phone_label) and idx > 0:
            return parts[idx - 1]
    if len(parts) >= 2:
        return parts[-1]
    return ""


def label_paragraph(text: str) -> str:
    match = re.match(r"^【([^】]+)】\s*(.*)$", text)
    if match:
        return f"**{match.group(1)}** {match.group(2)}".strip()
    return text


def build_markdown(data: dict) -> tuple[str, str]:
    items = data["content"]
    title_idx, title_item = first_non_empty(items)
    if title_item is None:
        raise RuntimeError("No article title found.")
    title = clean_text(title_item["text"])

    subtitle_idx, subtitle_item = first_non_empty(items, title_idx + 1)
    subtitle = clean_text(subtitle_item["text"]) if subtitle_item else ""

    duplicate_idx = find_duplicate_title(items, title, (subtitle_idx or title_idx) + 1)
    body_items = items[(subtitle_idx or title_idx) + 1 : duplicate_idx]
    meta_items = items[duplicate_idx + 1 :] if duplicate_idx is not None else []

    author_info = ""
    meta_blocks: list[str] = []
    centered_meta_count = 0
    author_prefix = "\u4f5c\u8005\uff1a"
    for item in meta_items:
        text = clean_text(item.get("text", ""))
        if not text or text in {title, subtitle}:
            continue
        if text.startswith(author_prefix):
            author_info = text
            continue
        if item.get("alignment") == "center" and not text.startswith("【"):
            centered_meta_count += 1
            label = "\u82f1\u6587\u9898\u540d" if centered_meta_count == 1 else "\u82f1\u6587\u526f\u9898"
            meta_blocks.append(f"**{label}** {text}")
        else:
            meta_blocks.append(label_paragraph(text))

    author = extract_author(author_info)

    lines: list[str] = []
    lines.append(f"### {title}" + (f" / {author}" if author else ""))
    if subtitle:
        lines.extend(["", f"## {subtitle}"])

    if meta_blocks:
        lines.append("")
        lines.extend(meta_blocks)

    lines.extend(["", "---[dot]", ""])

    for item in body_items:
        text = clean_text(item.get("text", ""))
        if not text:
            continue
        if text in {title, subtitle}:
            continue
        if is_section_heading(text):
            lines.extend([f"## {text}", ""])
        else:
            lines.extend([text, ""])

    footnotes = data.get("footnotes", [])
    if footnotes:
        lines.extend(["---[notes]", ""])
        for note in footnotes:
            mark = note_mark(note.get("id", ""))
            note_text = clean_text(note.get("text", ""))
            lines.extend([f"^[{mark} {note_text}]", ""])
        lines.append("---[/notes]")

    if author_info:
        lines.extend(
            [
                "",
                "---[bio-title:\u4f5c\u8005\u7b80\u4ecb]",
                "",
                f"[bio:{author_info}]",
                "",
                "---[/bio]",
            ]
        )

    markdown = "\n".join(lines).replace("\n\n\n", "\n\n").strip() + "\n"
    report = build_report(markdown, data, author_info)
    return markdown, report


def build_report(markdown: str, data: dict, author_info: str) -> str:
    issues: list[str] = []
    if "\u200d" in markdown or "\u200b" in markdown:
        issues.append("\u5b58\u5728\u96f6\u5bbd\u5b57\u7b26\uff0c\u5df2\u5728\u6210\u54c1\u4e2d\u6e05\u7406\u3002")
    if re.search(r"\d{11}", author_info):
        issues.append("\u4f5c\u8005\u4fe1\u606f\u542b\u624b\u673a\u53f7\uff0c\u516c\u4f17\u53f7\u53d1\u5e03\u524d\u5efa\u8bae\u786e\u8ba4\u662f\u5426\u4fdd\u7559\u3002")
    if data.get("image_count", 0):
        issues.append("\u6e90\u6587\u6863\u542b Word \u5185\u5d4c\u56fe\u7247\uff0c\u56e0\u672a\u63d0\u4f9b\u56fe\u5e8a URL\uff0c\u5df2\u6309\u89c4\u5219\u4e0d\u5199\u5165\u6b63\u6587\u3002")
    if not issues:
        issues.append("\u672a\u53d1\u73b0\u660e\u663e\u95ee\u9898\u3002")
    return "\u6821\u5bf9\u63d0\u9192\uff1a\n" + "\n".join(f"- {issue}" for issue in issues) + "\n"


def inline_markup(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\^([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])", r"<sup>\1</sup>", escaped)
    return escaped


def render_preview(markdown: str, title: str) -> str:
    parts: list[str] = []
    in_notes = False
    in_bio = False

    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "---[dot]":
            parts.append('<section style="margin:28px 8px;text-align:center;color:#b7c5d8;letter-spacing:4px;">······</section>')
            continue
        if line == "---[notes]":
            in_notes = True
            parts.append('<section style="margin:28px 8px 18px;padding:14px 12px;background:#f7f9fb;border-left:3px solid #7b9fc7;">')
            parts.append('<p style="margin:0 0 10px;color:#365f8f;font-size:14px;font-weight:700;">注释</p>')
            continue
        if line == "---[/notes]":
            in_notes = False
            parts.append("</section>")
            continue
        if line.startswith("---[bio-title:"):
            in_bio = True
            label = line[len("---[bio-title:") : -1]
            parts.append('<section style="margin:30px 8px 10px;padding-top:18px;border-top:1px solid #d8e1ec;">')
            parts.append(f'<p style="margin:0 0 12px;color:#365f8f;font-size:15px;font-weight:700;">{html.escape(label)}</p>')
            continue
        if line == "---[/bio]":
            in_bio = False
            parts.append("</section>")
            continue
        if line.startswith("[bio:") and line.endswith("]"):
            text = line[5:-1]
            parts.append(f'<p style="margin:0 8px 14px;line-height:1.8;color:#666;font-size:14px;text-align:justify;">{inline_markup(text)}</p>')
            continue
        if line.startswith("### "):
            text = line[4:]
            if " / " in text:
                head, author = text.rsplit(" / ", 1)
                parts.append(f'<h1 style="margin:18px 8px 8px;text-align:center;font-size:22px;line-height:1.45;color:#24364b;font-weight:700;">{inline_markup(head)}</h1>')
                parts.append(f'<p style="margin:0 8px 18px;text-align:center;color:#6f7d8b;font-size:14px;">{inline_markup(author)}</p>')
            else:
                parts.append(f'<h1 style="margin:18px 8px 18px;text-align:center;font-size:22px;line-height:1.45;color:#24364b;font-weight:700;">{inline_markup(text)}</h1>')
            continue
        if line.startswith("## "):
            text = line[3:]
            parts.append(f'<h2 style="margin:30px 8px 18px;text-align:center;font-size:17px;line-height:1.65;color:#365f8f;font-weight:700;">{inline_markup(text)}</h2>')
            continue
        if in_notes and line.startswith("^[") and line.endswith("]"):
            text = line[2:-1]
            parts.append(f'<p style="margin:0 0 8px;line-height:1.7;color:#666;font-size:12px;text-align:justify;">{inline_markup(text)}</p>')
            continue
        if not in_bio:
            parts.append(f'<section style="line-height:2em;margin:0 8px 14px;text-align:justify;"><span style="font-size:15px;font-family:宋体,SimSun,serif;color:#2f3437;">{inline_markup(line)}</span></section>')

    body = "\n".join(parts)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} - 谓无名公众号预览</title>
</head>
<body style="margin:0;background:#eef2f6;">
  <main style="max-width:720px;margin:0 auto;background:#fff;min-height:100vh;padding:26px 18px 48px;box-sizing:border-box;">
{body}
  </main>
</body>
</html>
"""


def validate(markdown: str) -> list[str]:
    errors: list[str] = []
    pairs = [
        (">>>", "<<<"),
        ("---[notes]", "---[/notes]"),
        ("---[bio-title:", "---[/bio]"),
    ]
    for start, end in pairs:
        if markdown.count(start) != markdown.count(end):
            errors.append(f"Unpaired marker: {start} / {end}")
    if "placeholder" in markdown.lower():
        errors.append("Placeholder text detected.")
    if re.search(r"word/media/|file://|\\\\", markdown):
        errors.append("Local file path detected in markdown.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_docx", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    args = parser.parse_args()

    extractor = load_extractor()
    data = extractor.extract_word_structure(args.input_docx)
    markdown, report = build_markdown(data)

    first_title = clean_text(next(item["text"] for item in data["content"] if clean_text(item.get("text", ""))))
    safe_name = re.sub(r'[<>:"/\\\\|?*\\s]+', "_", first_title).strip("_")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    md_path = args.output_dir / f"{safe_name}_谓无名公众号排版.md"
    html_path = args.output_dir / f"{safe_name}_谓无名公众号预览.html"
    report_path = args.output_dir / f"{safe_name}_校对提醒.txt"

    md_path.write_text(markdown, encoding="utf-8", newline="\n")
    html_path.write_text(render_preview(markdown, first_title), encoding="utf-8", newline="\n")
    report_path.write_text(report, encoding="utf-8", newline="\n")

    errors = validate(markdown)
    print(f"markdown={md_path}")
    print(f"html={html_path}")
    print(f"report={report_path}")
    print(f"footnotes={len(data.get('footnotes', []))}")
    print(f"images={data.get('image_count', 0)}")
    if errors:
        print("validation=failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("validation=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
