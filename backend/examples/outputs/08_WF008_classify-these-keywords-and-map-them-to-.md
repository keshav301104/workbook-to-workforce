# Excel test question (asks for keyword list)

**User request:** “Classify these keywords and map them to pages.”

## Selected workflow
**WF008 — SEO Keyword Classification** (confidence 97%, lexical router)

> Matched on: classify, keywords, map, pages.

**Inputs:** Keyword file: `keywords.csv` · Site categories: `categories.csv`

## Steps executed
1. ✓ **Keyword list provided?** (decision) — `missing(inputs.keyword_file) and missing(inputs.keywords)` → true → ask
   - ❓ **Asked the user:** Attach the keyword CSV to classify (or use the sample list). You can also paste keywords as “keywords: a, b, c”.
   - ↺ resumed from step `have_keywords` with the user's answer
2. ✓ **Keyword list provided?** (decision) — `missing(inputs.keyword_file) and missing(inputs.keywords)` → false → continue
3. ✓ **Read keywords** (`load_table`) — Loaded 27 rows × 3 columns from keywords.csv
4. ✓ **Remove duplicates** (`dedupe_rows`) — 25 unique, 2 duplicate(s) removed
5. ✓ **Classify search intent** (`llm_classify` · rules) — Labels: commercial 14, transactional 5, informational 3, navigational 3
6. ✓ **Load site categories** (`load_table`) — Loaded 8 rows × 3 columns from categories.csv
7. ✓ **Map keywords to categories** (`llm_map` · rules) — Mapped 25 rows to 8 target(s)
8. ✓ **Identify high-priority keywords** (`compute_column`) — Computed priority_score, target_page for 25 rows
9. ✓ **Assign priority** (`rank_bucket`) — Buckets: High 9, Medium 8, Low 8
10. ✓ **Sort by priority** (`sort_rows`) — Sorted by priority_score (desc)
11. ✓ **Export results** (`export_table`) — Exported 25 rows to keyword_report.csv

## Result
**25 keywords classified · 9 high priority** — status: `completed`

_2 duplicates removed from 27 keywords_

Keywords read: **27** · Duplicates removed: **2** · Transactional: **5** · Commercial: **14** · Informational: **3** · Navigational: **3**

**Keyword report**
| Keyword | Intent | Category | Priority | Score | Recommended page | Volume | Difficulty |
|---|---|---|---|---|---|---|---|
| linen shirt | commercial | Shirts | High | 8338 | /collections/shirts | 14800 | 42 |
| merino wool sweater | commercial | Knitwear | High | 5388 | /collections/knitwear | 9900 | 47 |
| waxed jacket | commercial | Outerwear | High | 4469 | /collections/outerwear | 8100 | 45 |
| chino trousers men | commercial | Trousers | High | 3667 | /collections/trousers | 6600 | 44 |
| wool throw blanket | commercial | Home | High | 3086 | /collections/home | 5400 | 40 |
| leather belt brown | commercial | Accessories | High | 2532 | /collections/accessories | 4400 | 39 |
| how to wash linen shirts | informational | Shirts | High | 2237 | /blogs/guides/how-to-wash-linen-shirts | 6600 | 18 |
| stoneware mug set | commercial | Home | High | 2215 | /collections/home | 3600 | 30 |
| best linen shirts 2026 | commercial | Shirts | High | 2066 | /collections/shirts | 3900 | 51 |
| cheap leather belt | transactional | Accessories | Medium | 2057 | /collections/accessories | 2900 | 41 |
| linen vs cotton shirt | commercial | Shirts | Medium | 1902 | /collections/shirts | 2900 | 22 |
| buy linen shirt online | transactional | Shirts | Medium | 1778 | /collections/shirts | 2400 | 35 |
| is merino wool itchy | informational | Knitwear | Medium | 1571 | /blogs/guides/is-merino-wool-itchy | 4400 | 12 |
| linen duvet cover queen | commercial | Home | Medium | 1412 | /collections/home | 2400 | 36 |
| merino sweater sale | transactional | Knitwear | Medium | 1377 | /collections/knitwear | 1900 | 38 |
| stoneware vs ceramic mugs | commercial | Home | Medium | 1299 | /collections/home | 1900 | 17 |
| halden discount code | transactional | Brand & Support | Medium | 1193 | /pages/help | 1300 | 9 |
| chinos vs trousers | commercial | Trousers | Low | 1076 | /collections/trousers | 1600 | 19 |
| how to rewax a waxed jacket | informational | Outerwear | Low | 835 | /blogs/guides/how-to-rewax-a-waxed-jacket | 2400 | 15 |
| best waxed jacket for rain | commercial | Outerwear | Low | 782 | /collections/outerwear | 1300 | 33 |
| waxed field jacket olive | commercial | Outerwear | Low | 465 | /collections/outerwear | 720 | 24 |
| halden login | navigational | Account | Low | 419 | /account/login | 880 | 5 |
| halden store miami | navigational | Brand & Support | Low | 273 | /pages/help | 590 | 8 |
| order wool throw blanket | transactional | Home | Low | 264 | /collections/home | 320 | 21 |
| halden returns policy | navigational | Brand & Support | Low | 226 | /pages/help | 480 | 6 |

**Duplicates removed**
| As written | Kept as |
|---|---|
| Linen Shirt  | linen shirt |
| linen  shirt | linen shirt |

- 📎 Keyword report (CSV) (25 rows)
