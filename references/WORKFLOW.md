# Walmart Listing 工作流

## 输入与范围

必填：1–20 个去重的竞品 Product ID、`target_country`（仅 US/CA/MX）、本品图片或文字资料。US 使用美式英语，CA 使用加拿大英语，MX 使用墨西哥西班牙语，不增加其他市场。

可选：自有/授权品牌、真实变体、禁用词；文案 Skill 默认不要求图片策划，设 `image_plan_required=false`；系统另行请求策划时才生成，策划是后续生图输入。没有品牌不编品牌，没有变体不补组合。只集中询问真正阻碍写作的事实；未知信息保留在 `unknowns`。

Product ID 应来自目标国家，不按长度或是否含字母猜测有效性。写作只支持 US/CA/MX；当前 Sorftime Walmart 关键词数据仅核实 US，依据与检查日期见 [SOURCE_CAPABILITIES.json](SOURCE_CAPABILITIES.json)。目标国家标签、当地语言或当地商品页面存在，都不能证明 Sorftime 返回的是当地数据。接口没有国家参数，不自行添加，也不删改 MX ID 的前导零或换成美国同款 ID。

采集前运行 `quality.py check-source RUN`。CA/MX 返回 unsupported_source_market 时停止完整关键词流程；用户明确要求重新核实接口覆盖时，可做有界的只读实测并保留原始结果，但仍不能将无数据解释成当地需求为零或把美国结果贴成当地结果。恢复条件是供应商明确开放同站数据并经真实查询核对，不是反复换 ID。

## 产物与命令

当前目录创建 `walmart_listing_<YYYYMMDD_HHmmss>/`（RUN），Skill 根目录为 SKILL；命令中均替换为绝对路径。仅需 Python 3 标准库，本地工具不联网。先读 [DATA_CONTRACT.md](DATA_CONTRACT.md) 获取字段和示例。

| 文件 | 用途 |
|---|---|
| 01_product_profile.json | 目标国家、输入 ID、本品事实及用户来源 |
| 02_kw_raw.json | 逐页原始响应、抽取指针、程序聚合结果 |
| 03_keyword_view.tsv / 03_keyword_groups.json | 全词视图与完整意图分组 |
| 03_keyword_decisions.json | 每个词唯一一条分类账本 |
| 03_kw_filtered.json / 03_kw_deferred.json / 03_kw_removed.json | 程序导出的可用/暂缓/剔除词池 |
| 04_kw_tagged.json | 带证据和标签的可用词 |
| 05_keyword_plan.json | Walmart 三个文案字段的分词计划及放弃原因 |
| 06_competitor_context.json | 可选竞品语境；不用时写 skipped 与原因 |
| 07_listing.json / 07_listing.md | 结构化与可读文案、图片策划 |
| 08_keyword_coverage.json | 程序计算的实际短语命中与隔离词泄漏 |
| 08_semantic_review.json | 简短语义复核及内容指纹 |

## 1. 确认本品事实

保存画像，包括 product_name/category、brand/brand_authorized、unknowns、forbidden_terms、variations 和 image_plan_required。类目字数例外使用 DATA_CONTRACT 的 content_standard；语义复核必须核对来源内容与实际类目及阈值一致，官方域名本身不构成已核实依据。

把用户文字、图片、文档分别记录为 sources；把确认的身份、材质、规格、数量、功能、场景拆成带 fact_id 的 facts，引用 source_ids。产品核心品名必须引用 identity_fact_ids，不能因扩词中缺席就删去。图片只能证明可见信息，不能据此猜材质、认证或性能。未知不等于已确认不存在。竞品和关键词仅作研究，不作为本品事实来源。

## 2. 逐 ID 采集、聚合

按 [SORFTIME_MCP.md](SORFTIME_MCP.md) 逐 ID、逐页查询，响应立即落盘。优先把完整 MCP 响应保存为文件，并导入为 page 对象：

```text
python3 SKILL/scripts/import_page.py RUN/evidence/traffic_page_1.json RUN/evidence/normalized_page_1.json --page 1
```

把返回的 page 对象放入 raw.by_product_id[ID].pages；脚本适配真实 data[].keyword.keyword，并保留原始响应。只将成功响应中的准确文本 `No data available.` 认作空页，其他错误、未知文本或损坏 JSON 不当成零词。页码与停止状态仍按分页协议记录。

```text
python3 SKILL/scripts/quality.py aggregate RUN
python3 SKILL/scripts/quality.py check-research RUN
```

所有输入 ID 都完成限定分页、无未解决错误、来源一致后才筛词。5 页截断必须披露；这不是穷尽全部关键词。已支持站点的零结果停止写作，可更换有效竞品；不支持站点不能用不断更换ID来掩盖能力缺失。不用其他平台或网页关键词补洞。

## 3. 三类词池

必须执行 [KEYWORD_GROUPS.md](KEYWORD_GROUPS.md) 的意图分组与写作前检查；下述逐词字段由分组工具填写，不能跳过分组直接手写最终词池。

```text
python3 SKILL/scripts/quality.py prepare RUN
```

在生成的账本中逐词填写完整搜索意图、分类、原因与事实引用，可将同意图词一起判断，但每个词保留独立记录：

- **eligible**：完整意图与本品身份/确认事实一致。必须有 fact_ids、relevance（high/relevant）和 intent。
- **deferred**：属性未知、用途未确认、品牌归属或相关性有歧义。必须写 promotion_condition；不进入文案、图片文案或关键词计划。
- **excluded**：完整意图不符、事实冲突、他人品牌/IP、禁用或明确噪声。记录具体原因。

保持原有目标语言筛选，但不得仅因低流量、短词、非 ASCII 字符或子串命中而剔除；拼写/语言身份有歧义先暂缓。`high` 指真实属性或场景缩小了搜索范围；单纯品类同义词为 `relevant`，不把 high 当搜索量。

```text
python3 SKILL/scripts/quality.py export RUN
```

程序验证每个原词恰好分类一次、事实引用有效，再导出三池与标签。不得手改导出池。新增事实或更换原始数据后运行 `rebind RUN`，重新确认 pending 判断并更新分组，再 apply-groups、export、check-keywords；旧理由保留作参考，旧审核不能自动延续。无需 Amazon 的复杂增量系统。

## 4. 排序与 Walmart 字段分配

依次使用真实可比热度指标、多竞品命中数量、原始顺序作为排序依据。不同指标不能直接混加，不把命中数量叫搜索量。需要时最多补查 20 个候选词详情并保存真实响应。

仅对 eligible 制定计划：标题可优先安排 1–2 个核心短语（建议，不作数量门槛）；Key Features 放真实属性词；描述承接其余合适词。所有可用词要么安排一次，要么放入 not_planned 并说明原因。可以放弃覆盖，不为塞词破坏可读性。核心品名、用户提供的事实仍可自然表达，不需要伪造为 Sorftime 返回词。

## 5. 可选竞品语境

仅在品牌或类别判定需要时，每个 ID 最多查询一次竞品详情，写 06 文件；需要识别品牌才能完成筛词时可提前执行这一步。新证据改变判断后重新 export。不得把竞品属性写进本品 facts。

## 6. 按 Walmart 规则写作

完整读取 [WALMART_COPY_RULES.md](WALMART_COPY_RULES.md)，必要时读 EXAMPLES.md。保持标题非空且不超过150字符、描述遵循通用150词段落要求（类目规则以官方依据为准），不强制以标题开头、3–10 条且每条至多 80 字符的 Key Features；不采用 Amazon 字段、五点格式或 A+。

在 JSON 的 claims 中为可核查声明登记原文片段、字段位置与 fact_ids；复合句涉及多个事实就引用全部必要事实。每个非空文案/图片策划字段都需要引用，不能仅给整份文案挂一个笼统事实。图片策划说明用中文，overlay_text 用目标语言，保持原有按需数量。变体只按输入清单展开实际标题供长度检查，保留原有模板交付，不建立 Amazon 父子体系统。

## 7. 本地审计、简短复核、交付

```text
python3 SKILL/scripts/quality.py audit RUN
python3 SKILL/scripts/quality.py review-template RUN
```

audit 分开记录计划字段命中与全部 eligible 的实际前台命中；not_planned 只表示未主动安排，不能把自然出现的词报成未使用。audit 实算完整短语命中（大小写、连字符/空格规范化），不把语义近似报成命中；未命中可填写 unused_reason 后重新 audit。暂缓/剔除词泄漏须修正，不为通过而无依据地改分类。剔除词只出现在“不要声称……”的中文策划里也会命中，改写为不重复该关键词的限制说明。

review-template 只生成 pending，绝不自动认定通过。逐项对照原始用户资料复核：

1. facts_and_claims：来源是否真实，全部实质性声明是否有充分依据，有无漏登声明；
2. keyword_intent：分类、完整意图、品牌和隔离状态是否正确；
3. walmart_copy：逐项核对标题、正文、Key Features、变体标题和图片文字的目标语言、自然程度、CA拼写/MX用语、数字单位、禁止声明与排序；无品牌时品名开头、无凑字数或堆词；语言信号检查仅拦截明显错标，不能替代这些判断；
4. variants_and_images：只含真实组合，属性匹配、图片文字一致、待补拍事项明确。

记录具体 notes 与 passed/failed。可以在同一执行中完成一次独立于写作步骤的复核，不要求额外代理或后端。脚本能验证引用存在，不能替代对事实含义的判断。输入、分类、计划或文案改动会使旧复核失效，应重新生成模板和复核。

```text
python3 SKILL/scripts/quality.py render RUN
python3 SKILL/scripts/validate_output.py RUN
```

render 从最终 JSON 生成固定顺序 Markdown，并披露市场证据与分页截断。验证失败按具体问题修正，最多两轮；仍未通过则报告未完成原因，不伪造成功。用户提供新事实后可继续原任务。正常交付 07_listing.md、07_listing.json、08_keyword_coverage.json，并说明是否有截断/来源未核实。

## 失败处理

同一页临时错误最多重试一次；仍失败则停止扩词并报告 ID、页码和脱敏错误，不生成最终 Listing。保留成功页面供恢复，不重建或伪造响应。缺页/部分成功不能自动降级为完整词集。事实不足无法达到原有写作规则时请用户补充，不凑字数或发明属性。修改已有任务失败时不得把旧 07 文件当作本次验收通过的成果。

## 仅在用户要求公开商品实测时

用户明确要求选择真实商品测试流程时，US 可用 `walmart_product_search_from_name` 选商品；CA/MX 实测须先从对应当地官方站点确定真实商品及原始ID，再核对 Sorftime，不能把商品名搜索返回的美国商品当成当地商品。画像设 `mode=public_product_demo`、target_product_id 和 test_authorization（用户测试请求的摘要），不设虚假品牌授权。sources 仅允许同一目标 ID 的 public_product，facts 用 source_reported，表示公开页面陈述而非实物验证；细节见 DATA_CONTRACT。正常 production 模式仍禁止将竞品公开信息写作本品事实。

测试可核对所选目标的官方商品页以补足身份与规格，网页不能补关键词。详情 title=null 时可核对同 ID 搜索结果与商品页，不编造标题、不把其他 ID 的说明挪用。测试报告强制标注用途，不直接作为用户新品上架文件；不自动发布。美国测试不能证明 CA/MX 数据可用。

## 用户明确要求的独立语言测试

当本次请求包含语言测试，但同站关键词不可用时，保留研究阻断记录与真实响应，可单独以目标商品资料生成 `language_test.json` 和 `language_test.md`，不得生成最终 07_listing.*、伪造三类关键词池或覆盖率。文件需标注 scope=language_test_only、keyword_research_status=unsupported_source_market，使用同一套 Walmart 标题、段落和 Key Features 限制、事实引用及图片策划规则。

```text
python3 SKILL/scripts/copy_checks.py RUN/language_test.json
```

该命令只检查字段、长度、计数和明显语言错标，不认证数据来源、事实充分性或当地表达自然程度。继续对照事实和本地化规则做语义复核，结果保存在 language_test_review.json。正文、标题、要点和图片文字都要复核；语言通过不代表关键词研究通过。
