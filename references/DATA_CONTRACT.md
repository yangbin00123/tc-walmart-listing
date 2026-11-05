# 精简数据契约

仅本地审计新增字段；上架字段保持 Walmart 原样。JSON 使用 UTF-8。下列示例是结构说明，不是产品事实。

## 产品画像

```json
{
  "target_country": "US",
  "product_ids": ["123"],
  "product_name": "Storage Bag",
  "brand": null,
  "brand_authorized": false,
  "image_plan_required": false,
  "forbidden_terms": [],
  "unknowns": ["防水性能未知"],
  "sources": [{"source_id":"s1","kind":"user_text","locator":"本次用户产品描述","excerpt":"用户提供的准确原文"}],
  "facts": [{"fact_id":"f1","text":"已确认的产品身份或属性","status":"confirmed","source_ids":["s1"]}],
  "identity_fact_ids": ["f1"],
  "variations": []
}
```

正常 production 模式来源 kind 仅 user_text/user_image/user_document；图片 excerpt 写直接观察，locator 指图片路径/附件定位；文档写路径和页码。保留用户原始资料供复核。variations 有值时每项为 `{"variant_id":"v1","attributes":{"color":"Blue"},"fact_ids":["f2"]}`，只保存已提供的真实组合。

## 原始数据与抽取

02 延续 Sorftime 来源、输入 ID、逐 ID pages 和聚合数据。每页必须包含：

```json
{
  "page": 1,
  "response": {"items": [{"term": "storage bag", "volume": 123}], "hasMore": false},
  "records": [{"record_pointer":"/items/0","keyword_pointer":"/term"}],
  "has_next": false,
  "next_page_evidence": "响应 hasMore=false"
}
```

response 为工具原始业务响应（对象、可解析 JSON 字符串或真实成功空页文本 `No data available.`）；不修改字段/指标。MCP 外层有文本包装时保留原始工具返回为旁证并抽取真实业务响应，不把示例字段强加给服务。record_pointer 从 response 定位完整记录；keyword_pointer 从该记录定位关键词，遵循 JSON Pointer 的 `~0`、`~1` 转义。records 必须枚举该页全部关键词记录；真实 Sorftime data[] 结构由程序按 /data/i 与 /keyword/keyword 全量核对，漏项、重复、重排均失败。import_page.py 还保存 mcp_response，校验器核对其文本与 response 相同。其他已确认结构的手工指针仍需语义复核，不能凭猜测改字段。

`has_next` 是 true/false/null；只有响应明确无下一页时填 false，并写 next_page_evidence。不明时 null，继续至其他停止条件。

每个 ID 状态：`pages`、`stop_reason`、`pagination_capped`、`error:null`。stop_reason 为 no_next_page/empty_page/repeated_page/no_new_keywords/max_pages。

02 顶层还需：

```json
{
  "source":"sorftime_mcp",
  "server":"sorftime-server",
  "tool":"walmart_product_traffic_terms",
  "marketplace":"Walmart US",
  "product_ids":["123"],
  "completed_product_ids":["123"],
  "complete":true,
  "market_verification":{"status":"unverified","evidence":"响应未提供国家，尚无来源确认"},
  "raw":{"by_product_id":{},"keyword_details":{}},
  "warnings":[]
}
```

将实际逐 ID 状态放入 by_product_id。verified 时增加 country。商品页面国家与关键词源国家分开核对：当地页面/用户确认只能证明目标商品站点，不能证明 Sorftime 连接器覆盖该站。当前来源能力仅US；CA/MX不允许通过填写verified绕过 SOURCE_CAPABILITIES 门禁。

aggregate 自动生成 keywords、raw.keyword_data、pagination。聚合记录包含原文、规范化键、按输入顺序的 source_product_ids、product_hit_count、first_seen_order，以及 sorftime_records（每项 product_id/page/record_pointer/原始 record）。指标保持在 record 内，不复制为未经说明的派生流量。keyword_details 保存可选热度补查原始响应。

## 分类账本与导出

prepare 自动生成 profile_sha256/raw_sha256 和 decisions，禁止手工改指纹绕过失效检查。必须按 KEYWORD_GROUPS.md 经 apply-groups 生成 `group_schema_version:1`，每条包含 intent_group、role、evidence。下面仅展示基础判断字段，不是可直接提交的完整账本。每个原词一条，顺序不变：

```json
{"keyword":"storage bag","decision":"eligible","reason_code":"identity_match","reason":"与产品身份一致","query_intent":"寻找收纳袋","fact_ids":["f1"],"relevance":"relevant","intent":"品类泛词"}
```

deferred 需 promotion_condition，例如“用户提供防水测试或明确产品说明”；excluded 需具体冲突原因。三池和 04 都由 export 写入完整来源记录与判断，不手写。画像/数据改变先 rebind，所有词转 pending，保留旧理由供重新确认。

## 计划与文案

05 严格使用四个键。每个 eligible 恰好出现一次，分配或不使用：

```json
{
  "title":[{"keyword":"storage bag"}],
  "key_features":[],
  "description":[],
  "not_planned":[{"keyword":"另一个真实可用词","reason":"重复意图，避免堆词"}]
}
```

计划词最终未命中时，在该条目补 unused_reason。不用为达到覆盖率而强塞词。

07 保留 marketplace、listing_language、brand、product_title、product_description、key_features、variation_title_template、image_plan、metrics。新增以下审计字段：

- `variant_titles`：无变体为 []，有变体按输入顺序写 `{"variant_id":"v1","title":"实际展开的标题"}`。
- `image_plan`：每项 `{"direction":"中文策划与补拍要求","overlay_text":"目标语言文字或空字符串"}`；按需数量，不固定 Amazon 套图结构。
- `claims`：`{"field":"key_features.0","text":"字段中准确存在的声明片段","fact_ids":["f1"]}`。
- 字段路径支持 product_title、product_description、key_features.0、variation_title_template、variant_titles.0.title、image_plan.0.direction、image_plan.0.overlay_text，索引从 0 开始。
- 每个可核查声明均需事实引用，每个非空内容字段至少一条引用。照片构图等非产品声明不需另造事实，但所在图片策划要引用展示产品的真实事实。
- `metrics` 保持 title_characters、description_words（含标题的整个描述）、key_feature_characters；段落按实际描述计词，不强制附加标题或排除标题文字。

08 覆盖文件由 audit 生成，不能手改 used/matched_text。planned 是计划字段的实际命中；actual_eligible 是全部可用词在前台文案中的实际位置，含未计划但自然出现的词；summary 分开统计两者。语义复核由 review-template 创建 pending，实际复核后填写状态与中文 notes；程序重算 fingerprints，修改上游后旧通过状态失效。指纹是失效检测，不是对来源真实性的密码学证明。

## 公开商品测试模式（仅用户明确要求时）

01 增加 `mode:"public_product_demo"`、`target_product_id`、`test_authorization`；`brand_authorized` 必须为 false，品牌只作现有商品身份引用，有品牌时需 brand_fact_ids。sources 的 kind 必须为 public_product，每项 product_id 必须等于 target_product_id，locator 指向实际目标页面或保存的同 ID 响应，excerpt 可为标明性质的事实摘要。每条 fact.status 必须是 source_reported，不冒充用户确认。

07 同样带 mode 和 target_product_id；标题保留所选商品真实品牌以便准确识别。08 覆盖与 Markdown 强制显示测试用途和目标 ID，不能据此声称用户有品牌授权。正常模式省略 mode 或设 production；公开来源不能在正常模式过关。

## 数据源能力与语言测试边界

SOURCE_CAPABILITIES.json 维护 research_countries（当前US）与 writing_countries（US/CA/MX），两者不可混用。不支持站点的实测记录可保留 target_country 与实际来源 marketplace=Walmart US；complete只代表分页调用完成，不代表目标站点验证成功。00_source_verification.json 记录 unsupported_source_market 及原始响应定位。

独立语言测试（需用户明确要求）写 language_test.*，JSON增加 scope=language_test_only、keyword_research_status=unsupported_source_market；使用07同样的文案字段与claims，但不创建关键词池或完整成功报告。copy_checks.py 与完整 validate_output.py 共用字段规则，独立命令输出 scope=copy_format_and_language_signals_only 和 keyword_research_verified=false。本地化与事实语义复核单独记录，不能冒充完整SEO验收。

## 有官方依据的类目字数例外

画像可选 content_standard：{ "product_type": "与category完全一致的类目", "description_min_words": 150, "source_url": "Walmart官方类目标准URL" }。仅在已读取且可核对的官方类目标准明确要求时填写；缺省使用通用150词。语义复核必须核实该URL正文确实支持所填阈值，域名检查本身不证明内容真实。此字段随画像指纹失效检查；系统映射相同阈值，不用固定150词覆盖。
