# WeChat Article Editor Syntax Rules

Use this reference only to map source document structure into the "谓无名" editor syntax. Preserve source wording exactly unless the user asks for rewriting.

## Structure

| Syntax | Use |
|---|---|
| `### 标题 / 作者` | Main title with author when both are explicit in source |
| `## 标题` | Section heading |
| `---[dot]` | Major divider that exists or is clearly implied by source structure |
| `>` | Blockquote/citation |

## Editor Notes

```markdown
>>>
编者按原文
<<<
```

## Notes

```markdown
---[notes]

^[① 注释原文]

---[/notes]
```

Inline note references such as `^①` should be preserved.

## Book Blocks

Use book blocks only when the source already provides a book/info block or the user asks to mark one. Do not search to complete missing fields.

```markdown
[book:封面URL|书名|作者|出版社|年份]
[enbook:封面URL|English Title|Author|Publisher|Year]
[jpbook:封面URL|書名|著者|出版社|年]
```

Rules:
- If cover URL is missing, leave the first field empty: `[book:|书名|作者|出版社|年份]`.
- Do not use placeholder URLs.
- Do not add `[待确认]` or `[信息缺失]` inside the article.
- Keep source-provided metadata as written, even if incomplete; report suspected issues in `校对提醒`.

## Extended Reading

```markdown
---[reading-title:延伸阅读]

[reading-book:书名|编者|译者|图片url]
[reading-enbook:Title|Editor/Author|Publisher|图片url]
[reading-jpbook:書名|編者|出版社|图片url]

---[/reading]
```

If `图片url` is missing, leave it empty. The editor will show a blank book-cover placeholder. Do not invent a URL.

## Images

| Syntax | Use |
|---|---|
| `![alt](url)` | Source contains a real hosted image URL |
| `[bio-img:url]` | Bio photo with real hosted URL |
| `[universal:url|第一行|第二行|...]` | Generic image block with real hosted URL |

Rules:
- Word embedded image targets such as `word/media/image1.png` are not hosted URLs.
- If no hosted URL exists, omit the image syntax entirely.
- Report omitted images after the formatted markdown.

## Bio

```markdown
---[bio-title:作者简介]

[bio:简介原文]

---[/bio]
```

Only include `[bio-img:url]` if a hosted URL is provided or present in source.

## Staff and Follow

```markdown
[staff:姓名|职位]

---[follow]
关注提示原文
---[/follow]
```

Use these only when the source contains matching content or a local workflow explicitly requires a fixed footer.

## Validation

Before delivery, check:
- Paired syntax markers are closed.
- No placeholder URL appears.
- No local image path appears as an article image URL.
- Original wording is preserved.
- Typos, grammar, punctuation, and political/compliance issues are reported separately under `校对提醒`.
