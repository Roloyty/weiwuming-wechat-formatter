# WeChat Article Editor Syntax Rules

Use this reference only to map source document structure into the "谓无名" editor syntax. Preserve source wording exactly unless the user asks for rewriting.

## Structure

| Syntax | Use |
|---|---|
| `### 标题 / 作者` | Optional chapter heading inside the body; never place it above the editor note |
| `## 标题` | Section heading; immediately followed by `---[dot]` |
| `---[dot]` | Required visual divider after every `##` heading |
| `>` | Blockquote/citation |

### Article Structure Order

Every article must follow this order:

1. **编者按** — `>>> ` / `<<<`, ~500 chars; first non-empty markdown content, with no article title above it
2. **正文** — body text with keyword blocks (books, persons, etc.) inline
3. **目录** (if any) — `---[toc]` ... `---[/toc]`
4. **注释** (if any) — `---[notes]` ... `---[/notes]`
5. **来源说明** — `---[note]` ... `---[/note]` block with push source attribution
6. **作者简介** — `---[bio-title:作者简介]` ... `---[/bio]`
7. **译者简介** (if any) — `---[bio-title:译者简介]` ... `---[/bio]`
8. **延伸阅读** — `---[reading-title:延伸阅读]` ... `---[/reading]`
9. **staff** — exactly two `[staff:...]` entries
10. **固定关注区** — `---[follow]` ... `---[/follow]`

### ## Heading Rule

- Every `##` section heading must be immediately followed by a separate `---[dot]` line.
- Do not add `---[dot]` after `###` subheadings.

## Editor Notes (编者按)

**Every article must begin with a 编者按.** It must be the first non-empty markdown content. Do not place the article title, author line, or other content above it.

```markdown
>>> 编者按内容（约500字）：概述文章主要内容，并进行简要评议，点出文章的学术意义或现实关怀，或提出值得进一步思考的问题。语气应与"谓无名"的编辑风格一致——审慎、有见地、保持开放。
<<<
```

Rules:
- The 编者按 must be approximately 500 Chinese characters.
- It must: (1) summarize the main content and key arguments; (2) provide brief editorial commentary.
- The 编者按 is written by the formatter, not copied from the source.

## Notes (注释/脚注)

```markdown
---[notes]

^[1 注释原文一]

^[2 注释原文二]

---[/notes]
```

### Syntax details (verified against editor source code)

- **Inline reference**: `^N` where N is an Arabic number 1–50, placed directly after the sentence it annotates (e.g. `……探讨了美国宪法问题；^1杰克……`). The editor preprocess auto-converts `^1` → `^①` (circled numbers ①–㊿) and the postprocess renders it as a blue superscript (`footnote-num` span). Do NOT use raw HTML `<sup>N</sup>` — it renders as a plain superscript without the editor's note styling and is a common cause of "文中序号格式不对" complaints.
- **Note entry**: inside `---[notes]`, every entry MUST be a single line in the exact format `^[N 内容]` — starts with `^[`, then the number, one space, the note text, ends with `]`. The editor converts `^[1 ` → `^[① ` automatically and renders matched lines as footnote items (blue circled number + gray text).
- **Plain lines inside `---[notes]` are NOT rendered as footnote items** — they pass through as ordinary paragraphs. A bibliography pasted as bare lines therefore shows no numbering and wrong styling. Wrap every entry as `^[N …]`.
- Entry numbers must correspond 1:1 with the inline `^N` references (same N, no gaps).
- Long notes (including ones containing URLs or mixed Chinese/English citations) must stay on a single source line — no internal line breaks.

### Footnote recovery from MinerU conversions

When the source is a MinerU-converted PDF, footnote contents are usually MISSING from `full.md` but preserved in the sibling `*_content_list.json` as `page_footnote` blocks (plus `ref_text` blocks for the bibliography). Before declaring footnotes lost:

- Parse `*_content_list.json`, collect all `type === "page_footnote"` blocks in page order.
- Distinguish the author-affiliation footnote (`∗ …`) from the numbered footnotes; the affiliation note is usually folded into the author bio, not the notes block.
- OCR may drop some entries' leading numbers (`N.`); recover each entry's number from its page order relative to the surviving numbered entries.
- The end-of-article 参考文献 list is usually 100% redundant with the recovered footnotes (every citation appears inside some footnote). Prefer the footnotes — they match the inline markers — and drop the bibliography to avoid duplication.

### Notes format validation (run after rendering)

- Count match: number of inline `^N` refs in the body == number of `^[N …]` lines in `---[notes]`.
- Rendered check: in the output HTML, count `footnote-item` divs and `footnote-num` spans — both must equal the expected N, with no gaps in the circled-number sequence (①…㉓ etc.).
- No residue: zero `<sup>` tags and zero bare `^数字` left in the rendered HTML.

## Source Note (来源说明)

Every article must include a `---[note]` block for push source attribution, placed after notes (if any) and before author bio.

```markdown
---[note]

- 本次推送内容为《书名》一书的"章节名"。

- 感谢XXX授权转载。

- 图片源于作者/互联网。

---[/note]
```

Rules:
- The three lines follow this pattern:
  1. 本次推送内容为《书名》一书的"章节名"（或"某某"文章）。— identifies the source work.
  2. 感谢XXX授权转载。— thanks the rights holder (出版社/作者/本人). If the content is original, omit this line.
  3. 图片源于作者/互联网。— credits image source. Use "作者" if images are from the author, "互联网" if from the web.
- Endnote entries within `---[note]` use `- ・ 内容` format.

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

**Every article must include an extended reading section** based on the article's content. Use `douban-mcp` `search-book` as the primary tool to find 2–5 relevant books and add them above the staff entries.

```markdown
---[reading-title:延伸阅读]

[reading-book:书名|作者|译者|封面URL]

---[/reading]
```

Rules:
- If `封面URL` is missing, leave it empty. The editor will show a blank book-cover placeholder. Do not invent a URL.
- Book recommendations must be factually accurate and relevant to the article's subject matter.
- Use web search to verify titles, authors and translators. Still check the publisher and year to make sure you are citing a real in-print edition and to fetch the matching cover — just do not print them in the block.
- **Format Rule**: Each field MUST be separated by `|` (pipe character). Never use `、`、`，` or any other character **in place of** `|` to separate fields. (`、` is still allowed *inside* the translator field to join multiple translators — see below.)
- **Each reading entry MUST be separated by a blank line.**

### 作者字段与译者字段

`[reading-book:]` 的第二字段是作者、第三字段是译者。两者格式如下：

- **作者字段只写姓名，不写"著"**。`著` 是默认情形，一律省略。多位作者用半角 `/` 分隔，不用 `、` 或 `，`。
- **编著加"编"**：编者、编著、主编的书，在姓名后空一格补 `编`。这是唯一保留的著作方式标记。
- **译者字段**：`译者名 译`，姓名与 `译` 之间空一格；多位译者用 `、` 分隔。引用原版时留空。

#### 国籍前缀

`[国籍]` 标注的是**跨语言关系**，方括号与姓名之间**不留空格**。判断分三步：

1. **引用的是原版（未经翻译）吗？** 是 → 作者不加国籍，译者字段留空。
2. **是译本？** 作者与译者**各按本人国籍**标注。
3. **中国人一律省略国籍。**

因此中译本只有作者带前缀（译者是中国人），而一本英文书的日译本，作者和译者**两边都带前缀**。

```markdown
中译本   [reading-book:中国人留学日本史|[日]实藤惠秀|谭汝谦、林启彦 译|https://xxx.jpg]
中译本   [reading-book:日本现代文学的起源|[日]柄谷行人|赵京华 译|https://xxx.jpg]
中文编著 [reading-book:浮世通鉴：日本大众文化史|[日]日文研项目组 编|党蓓蓓 译|https://xxx.jpg]
中文原著 [reading-book:韩国现代政治史|咸在凤||]
外译外   [reading-book:思想戦：大日本帝国のプロパガンダ|[英]Barak Kushner|[日]井形彬 译|https://xxx.jpg]
原版     [reading-book:日本映画は信頼できるか|四方田犬彦||]
```

「外译外」条即 Barak Kushner *The Thought War* 的日译本（明石書店，2016）：作者是英语世界学者标 `[英]`，译者井形彬是日本人标 `[日]`，两者都不是中国人，所以都不省略。

#### 人名用哪种写法

- **中译本 → 用中译本署名的中文译名**：`[美]约翰·W·道尔`、`[日]实藤惠秀`。
- **其余情形（外译外、原版）→ 一律用本人原名**，不使用所引版本的音译或转写。上例的日译本封面署名是片假名「バラク・クシュナー」，条目仍写 `Barak Kushner`；译者井形彬本人原名即汉字，照写。

```markdown
✅ [reading-book:思想戦：大日本帝国のプロパガンダ|[英]Barak Kushner|[日]井形彬 译|https://xxx.jpg]
❌ [reading-book:思想戦：大日本帝国のプロパガンダ|[英]バラク・クシュナー|[日]井形彬 译|https://xxx.jpg]
```

错误写法：`|[日] 实藤惠秀 著|`（方括号后多空格、多"著"）、`|柄谷行人、莲实重彦|`（多作者应用 `/`）、`|赵京华|`（漏"译"）、`|Barak Kushner|井形彬 译|`（外译外漏掉两侧国籍）。

### 语法选择：延伸阅读一律用 `reading-book`

**延伸阅读不展示出版社。** 无论中译本还是外文原版，一律使用：

```markdown
[reading-book:书名|作者|译者|封面URL]
```

`[reading-jpbook:書名|著者|出版社|封面URL]` 与 `[reading-enbook:Title|Author|Publisher|封面URL]` 的第三字段是**出版社**，与本栏体例不符，**不要用在延伸阅读里**；它们保留给正文内联书目。

**未有中译本的外文书**：书名保留原文，译者字段留空。若引用的是该书**原版**，作者不加 `[国籍]`；若引用的是它在第三国的**译本**（如英文书的日译本），则按上文「国籍前缀」为作者和译者两侧都标注。

```markdown
[reading-book:日本映画は信頼できるか|四方田犬彦||]
[reading-book:ハリウッド映画史講義――翳りの歴史のために|蓮實重彦||]
```

## Keyword Blocks

**Identify key persons, books, events, and photos mentioned in the article.** Search the web for accurate details and insert the appropriate syntax block **immediately after the paragraph where the keyword is first mentioned**.

### Persons

```markdown
[universal:图片URL|姓名（生年~ 卒年）|身份/简介]
```

The first text field is automatically bold. Put verified birth/death years immediately after the name: `姓名（生年~ 卒年）`; for living persons use `姓名（生年~）`. **The year separator is the tilde `~`** — never a hyphen or dash (`-`, `–`, `—`) — **and exactly one space follows the tilde whenever a death year comes after it**: `舒群（1913~ 89）`, not `舒群（1913~89）`. A living person's name ends right after the tilde, with no trailing space. When the death year shares its first two digits with the birth year, drop those two digits: `舒群（1913~ 89）`, not `舒群（1913~ 1989）`. Write both years in full when the leading digits differ (`钱谦益（1582~ 1664）`) or when either year has fewer than four digits (`李白（701~ 762）`). Keep dates out of the second field, which contains identity and contribution only. Never invent a missing year, and do not add Markdown `**`.

### Books

```markdown
[book:封面URL|书名|作者|出版社|年份]
[enbook:封面URL|English Title|Author|Publisher|Year]
[jpbook:封面URL|書名|著者|出版社|年]
```

**Important Format Rule**: Each field MUST be separated by `|` (pipe character). Do NOT use `、` or any other delimiter to combine author, publisher, and year into a single field.

- ❌ Wrong: `[jpbook:https://xxx.jpg|书名|作者、出版社、年份]`
- ✅ Correct: `[jpbook:https://xxx.jpg|竹内好全集|竹内好|岩波書店|2005]`

### Events

```markdown
[universal:图片URL|事件名称|简要说明]
```

### Photos and Artworks

```markdown
[origin:图片URL|图说第一行|图说第二行|更多说明...]
```

Use `[origin:]` for archival photos, artworks, horizontal images, or any image whose intrinsic width/height ratio must be preserved. It renders at the image's intrinsic size and proportion, shrinking only when it exceeds the article width. Its first text field is automatically bold; do not add `**`.

### Movies / TV Shows

**If a `[universal:...]` block contains a title that is a movie or TV show, use `douban-mcp` `search-movie` to look up its details and fill in the fields.**

```markdown
[universal:封面URL|《片名》|导演：导演名，编剧：编剧名|上映：YYYY，片长：NN 分钟]
```

Movie/TV posters and advertisements stay on `[universal:]`, which uses the standard card image size. The title field is automatically bold.

Rules:
- Use `douban-mcp` `search-movie` with the title as keyword (`q`).
- Fill in: cover image URL, title, director, screenwriter, release year, and runtime.
- The title field contains only the work title (normally `《片名》`); do not append `海报`.
- Put director and screenwriter in the same field so they render on one line: `导演：...，编剧：...`. Use full-width colons and a Chinese comma exactly as shown. Join multiple names within either role with `/`; retain `等` when the source or verified credit is intentionally non-exhaustive. Do not replace the screenwriter with cast or voice actors. If one person holds both roles, name that person in both roles.
- For movies, the release year and runtime MUST occupy one field: `上映：YYYY，片长：NN 分钟`.
- For TV shows, use one field: `首播：YYYY，单集片长：NN 分钟，共 NN 集`; omit the episode count only when it cannot be verified.
- Omit synopsis, historical context, and editorial explanation by default. Only when the user explicitly requests such information, put it in a later `|`-separated field, normally `说明：...`; never append it to the release/runtime field.
- Correct: `[universal:https://.../poster.jpg|《新世纪福音战士》|导演：庵野秀明/鹤卷和哉等，编剧：庵野秀明/榎户洋司等|首播：1995.10.4，单集片长：24 分钟，共 26 集]`
- Incorrect: `[universal:https://.../poster.jpg|《东京物语》海报|导演：小津安二郎，编剧：野田高梧、小津安二郎|上映：1953，片长：135 分钟|简介：家庭剧]`
- If the search result is a TV series rather than a movie, still use `search-movie` (it covers both); optionally also call `list-tv-reviews` for additional context.
- If no cover URL is found, leave it empty.

Rules:
- Use `douban-mcp` `search-book` as the primary tool for book lookups; use `douban-mcp` `search-movie` for movie/TV lookups; use web search for persons, events, and other non-book/non-movie keywords.
- If a hosted image URL cannot be found, leave the URL field empty. Do not invent URLs.
- Insert the keyword block right after the paragraph where the keyword first appears, not at the end of the article.
- If uncertain about factual accuracy, report in `校对提醒` rather than writing potentially incorrect data.

## Images

| Syntax | Use |
|---|---|
| `![alt](url)` | Source contains a real hosted image URL |
| `[bio-img:url]` | Bio photo with real hosted URL |
| `[universal:url|第一行|第二行|...]` | Standard-size person/poster/advertisement card; first line auto-bold |
| `[origin:url|第一行|第二行|...]` | Intrinsic-proportion photo/artwork card; first line auto-bold |

Rules:
- Word embedded image targets such as `word/media/image1.png` are not hosted URLs.
- If no hosted URL exists, omit the image syntax entirely.
- Report omitted images after the formatted markdown.
- Never add Markdown `**` around the first text field of `[universal:]` or `[origin:]`; the editor emits `<strong>` automatically.
- Parenthesized metadata inside these cards (for example `（某某博物馆藏）`) inherits the same auxiliary gray as the surrounding card metadata.

## Bio

```markdown
---[bio-title:作者简介]

[bio:简介原文]

---[/bio]
```

Only include `[bio-img:url]` if a hosted URL is provided or present in source.

The author bio is the first bio block after `---[note]`. Put the translator bio after the author bio when present. Move source bio wording into these blocks; do not leave duplicate bios in the body.

## Staff and Follow

**Every article must end with two staff entries and the fixed follow section.**

```markdown
[staff:作者姓名|编辑]

[staff:春生、|审校]

---[follow]

东亚视角 全球视野

寻找东亚论述的"虫洞"与"黑洞"

点击下图关注"谓无名"

---[/follow]
```

Rules:
- `[staff:作者姓名|编辑]` — fill with the actual author name(s) from the source document.
- `[staff:春生、|审校]` — the 审校 (reviewer) **always** defaults to `春生、`.
- The fixed follow section is **mandatory for every article**, regardless of whether the source contains it.
- Do not modify the follow section text — it is a fixed footer.

## Validation

Before delivery, check:
- Paired syntax markers are closed.
- No placeholder URL appears.
- No local image path appears as an article image URL.
- Original wording is preserved.
- **编者按** is present (~500 chars) as the first non-empty content; no article title appears above it.
- Every `##` heading is immediately followed by `---[dot]`; `###` headings are not.
- **Article structure order** is exact: 编者按 → 正文 → 目录(如有) → 注释(如有) → 来源说明(`---[note]`) → 作者简介 → 译者简介(如有) → 延伸阅读 → 两条 staff → 固定关注区.
- **`---[note]` source attribution** is present with push source info.
- **Two staff entries** are present: author as 编辑, `春生、` as 审校.
- **Fixed follow section** is present at the end of the article.
- **Extended reading section** is present above staff entries with relevant book recommendations.
- **Keyword blocks** are inserted after relevant paragraphs for key persons, books, events, and photos.
- `[universal:]` is used for standard cards/posters/ads; `[origin:]` is used for photos/artworks that must preserve intrinsic proportions; neither syntax contains `**` in its first text field.
- Every person card puts verified birth/death years immediately after the name, with **one space after the tilde before the death year** (`舒群（1913~ 89）`; a living person's `姓名（生年~）` has nothing after the tilde), and does not repeat them in the description.
- Every movie/TV poster card uses the bare work title without `海报`, puts `导演：...，编剧：...` in one field/rendered line (multiple names joined with `/`), keeps `上映/首播` and `片长` on one line, and omits synopsis/context unless explicitly requested.
- Typos, grammar, punctuation, and political/compliance issues are reported separately under `校对提醒`.
