# Sorftime Walmart MCP

## 目录

1. 允许的工具
2. 分页协议
3. 聚合协议
4. 输出结构与门禁

## 1. 允许的工具

主扩词工具：

```text
walmart_product_traffic_terms(product_id=<单个 ID>, page=<从 1 开始>)
```

- 每次只能传一个 `product_id`。
- 每页最多 20 条，按工具真实返回为准。
- 返回该商品近期获得曝光的 Walmart 搜索关键词。

可选补充：

```text
walmart_keyword_detail(keyword=<候选词>)
walmart_product_detail_by_product_id(product_id=<单个 ID>)
```

`walmart_keyword_detail` 仅补充少量候选词的真实热度证据；`walmart_product_detail_by_product_id` 仅补充品类与品牌过滤语境。二者都不能替代反查工具。

禁止使用卖家精灵、`laochen-cli expand`、Amazon `product_traffic_terms`、网页搜索、直接 HTTP 请求 Sorftime 或其他数据源回填关键词。用户明确要求选择公开商品测试时，可额外调用 walmart_product_search_from_name 找目标；官方商品页仅核对该目标事实，不参与扩词。

## 2. 分页协议

对去重后的每个 Product ID 独立执行：

1. 从 `page=1` 开始。
2. 每页响应立即原样保存。
3. 遇到以下任一条件停止该 ID：
   - 工具明确返回无下一页；
   - 返回空记录；
   - 当前页记录签名与已保存页完全重复；
   - 当前页没有任何新关键词；
   - 已完成第 5 页。
4. 达到第 5 页且响应仍暗示有更多结果时，记录 `pagination_capped: true`；这仍可视为按 Skill 上限完成，但必须在交付中披露。
5. 调用错误时对同一 ID、同一页重试 1 次；再次失败则整个扩词阶段失败。

不要并行混写同一个 ID 的页码，也不要把不同 ID 的响应合并成一次伪造调用。可以按 ID 顺序调用以确保审计链清晰。

## 3. 聚合协议

关键词规范化仅用于去重键：

- Unicode NFKC；
- 去除首尾空白；
- 连续空白折叠为一个空格；
- 使用 Unicode casefold 比较（兼容英语和西班牙语）；
- 不做词干化，不合并不同短语，不自动纠正拼写。

每个唯一关键词保留：

- 首次出现的原文 `keyword`；
- `normalized_keyword`；
- 按输入顺序排列的全部 `source_product_ids`；
- `product_hit_count`；
- 该词的全部原始 `sorftime_records`；
- `first_seen_order`；
- Sorftime 返回的搜索量、排名、曝光时间等真实字段，字段缺失时保持缺失或 `null`。

严禁把 `product_hit_count` 写成流量，也不得推算或编造搜索量。若同一真实指标在多条记录中不同，保留逐条值并在派生字段注明所用汇总方法。

## 4. 输出结构与门禁

`02_kw_raw.json` 的可执行结构见 [DATA_CONTRACT.md](DATA_CONTRACT.md)。逐页保存原始响应与关键词记录指针后，用 `quality.py aggregate RUN` 生成统一关键词与来源链，再用 `check-research` 检查。不要手工汇总指标或重建原始响应。

市场来源使用 market_verification 显式记录 verified/unverified 及证据。当前 SOURCE_CAPABILITIES.json 的 Sorftime Walmart 研究范围为 US；CA/MX 完整流程直接阻断，不能只写 unverified 后继续。当地页面只证明商品属于该站，不证明连接器有该站曝光词。

进入过滤/写作阶段前同时满足：

- `complete` 为 `true`；
- `product_ids` 与输入去重列表顺序一致；
- `completed_product_ids` 与 `product_ids` 完全一致；
- 每个 ID 至少有第 1 页原始响应与明确 `stop_reason`；
- 每个 ID 的 `error` 为 `null`；
- `raw.keyword_data` 可追溯到 `raw.by_product_id` 的原始记录。

任一条件不满足就停止，不得输出 Listing。

## 已实测的响应形状

流量响应 MCP content 中的 text 为 JSON，关键词位于 data[i].keyword.keyword，搜索量位于 data[i].keyword.search_volume；周排名和曝光占比是不同指标，不能替代月搜索量。也可能出现不同 update 日期，排序时保留日期，不伪装同日数据。

空页可能只返回纯文本 `No data available.`。用 import_page.py 读取保存的完整 MCP 响应，自动生成记录指针并拒绝 isError、未知文本和损坏响应。保留原文，不手写空数组替换。少于20条但没有明确停止信号时继续请求下一页；本次真实样例为20、20、20、7、空页。

## 站点实测结论（2026-10-23）

Walmart 写作目标仍仅 US/CA/MX。Sorftime 官网将 Walmart 标为美国站，工具也没有国家参数。真实 CA 商品 30GTMG201YEB 与 MX 商品 00941420221690 的详情、第一页关键词均返回 No data available.；CA商品名探查返回 walmart.com 商品。当前不能宣称已取得 CA/MX 同站关键词。记录查询完成、记录数为零与站点能力不足三件不同的事，不把零响应当作零搜索需求。

依据：https://www.sorftime.com/ 。不要把该页 Amazon 的多国支持列表用于 Walmart。今后更新能力需新的供应商范围说明与同站真实查询证据，不以本地标签或跨境配送地址判断。
