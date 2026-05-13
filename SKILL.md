---
name: wechat-formatter
description: |
  Convert uploaded .doc/.docx files or pasted text into WeChat article markdown using the "谓无名" editor syntax.
  Use when the user uploads Word documents, pastes article text, asks to format for WeChat, add syntax markers,
  排版文章, or convert academic/articles into the custom WeChat editor markdown. The skill preserves source content,
  extracts Word structure, and produces editor-ready markdown without inventing missing information or image URLs.
compatibility:
  - Python 3 standard library for .docx OOXML extraction
  - LibreOffice/soffice for legacy .doc normalization when available
  - Codex file read/write capabilities
---

# WeChat Article Formatter

Convert Word documents and pasted text into markdown for the "谓无名" WeChat article editor.

## Core Rules

- Preserve the uploaded document's content, order, wording, punctuation, names, dates, and citations as faithfully as possible.
- Do not rewrite, polish, summarize, expand, translate, or fact-complete the article unless the user explicitly asks.
- Do not search online to fill missing book/person/publication data unless the user explicitly asks for research or fact completion.
- Do not invent placeholders such as `https://placeholder`, `[待确认]`, or `[信息缺失]` in the formatted article.
- If an image has no usable hosted URL, do not output standalone image syntax for it.
- For book/reading-book blocks that are already present in the source but lack a cover URL, leave the image field empty, e.g. `[book:|书名|作者|出版社|年份]`; the editor will render its blank cover placeholder.
- If typos, grammar issues, punctuation issues, or political/compliance risks are found, keep the formatted article faithful to the source and report the issues after the markdown under `校对提醒`.

## Workflow

1. Detect input type.
   - For `.docx`, run `python scripts/extract_docx.py <file.docx>`.
   - For legacy `.doc`, use the same script. It detects the OLE container and tries LibreOffice conversion to `.docx` before extraction.
   - For pasted text, analyze the text directly.

2. Analyze structure.
   - Preserve paragraph order from the extraction JSON `content` array.
   - Use style hints, heading levels, alignment, bold runs, tables, footnotes, endnotes, and image relationships only as formatting clues.
   - Treat tables as source content. Convert simple tables to readable text blocks; if a table is structurally important, preserve rows in markdown table form.

3. Apply editor syntax. Read `references/syntax_rules.md` when exact syntax is needed.
   - Main article title or chapter heading: `### 标题 / 作者` when the source clearly contains both.
   - Section heading: `## 标题`.
   - Major visual divider from source: `---[dot]`.
   - Editor note: wrap source editor note content with `>>>` and `<<<`.
   - Blockquote: `> 原文`.
   - Notes: `---[notes]` ... `---[/notes]`; note entries use `^[① 内容]`.
   - Bio: `---[bio-title:作者简介]`, `[bio:原文]`, `---[/bio]`.
   - Staff credit: `[staff:姓名|职位]`.
   - Follow section: use `---[follow]` ... `---[/follow]` only when source content contains a follow prompt or the fixed footer is required by the local editor workflow.

4. Handle images.
   - Extracted Word image relationships are local package targets, not hosted URLs.
   - Do not emit `![alt](...)`, `[bio-img:...]`, or `[universal:...]` for local package targets unless the user provides a real hosted URL.
   - If the source text already contains a hosted image URL, preserve it in the appropriate syntax.
   - If a book block is needed and there is no cover URL, leave the first image field empty rather than using a placeholder URL.
   - At the end, report omitted images by position or nearby paragraph when possible.

5. Validate before delivery.
   - No placeholder URLs or invented missing-data markers are present.
   - No unsupported local image paths are emitted as article images.
   - Syntax markers are paired: `>>>`/`<<<`, `---[notes]`/`---[/notes]`, `---[reading-title:]`/`---[/reading]`, `---[bio-title:]`/`---[/bio]`.
   - The result follows the source document order.
   - Suspected typos, grammar, punctuation, and political/compliance issues are listed separately, not silently corrected.

## Reporting Format

Return:

```markdown
排版结果：

<editor-ready markdown>

校对提醒：
- 未发现明显问题。
```

If issues exist, list them with source snippets and a concise reason:

```markdown
校对提醒：
- 可能错别字："..."，建议核对是否应为 "..."。
- 标点疑点："..."，中英文标点混用，建议人工确认。
- 政治/合规风险："..."，建议人工复核表述是否符合发布要求。
- 图片处理：第 N 处图片未提供图床链接，已按规则不写入正文。
```

## Word Extraction Notes

The bundled extractor adopts the `minimax-docx` approach:

- Detects file signature instead of trusting extensions.
- Treats `.docx` as an OOXML ZIP package.
- Converts `.doc` to `.docx` through LibreOffice when available.
- Uses Python standard-library XML parsing instead of `python-docx`.
- Extracts paragraphs, style names, alignment, run bold/italic/size hints, tables, footnotes/endnotes, and image relationships.

If `.doc` conversion fails or LibreOffice is unavailable, ask the user for a clean `.docx` export.
