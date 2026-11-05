# Walmart Listing 写法示例

示例只说明结构与质量标准，不是可复用商品事实。

## 标题

好：

```text
ABCDEF Women's Mary Jane Pumps, Pointed Toe Low Kitten Heel
```

- 品牌在前，品类明确，属性自然，不超过150字符。
- 没有连续堆叠 `shoes heels pumps footwear` 等同义词。

差：

```text
Best Women's Shoes Pumps Heels Dress Shoes Sexy Wedding Shoes Sale
```

- 含极限/促销词，重复品类词，读起来像关键词列表。

## 描述

好的方向：自然使用商品名称，以通用至少150词的段落陈述已确认的材质、鞋跟高度、鞋头与扣带结构、适用场景、颜色和尺码。语气帮助买家判断，不声称“绝不会疲劳”或“适合所有人”。

差的方向：从竞品页面复制材质和尺寸；用 `premium`、`perfect`、`must-have` 等空洞形容词凑字数；加入未确认的退换货或质量保证。

## Key Features

好：

```text
Upper Material: Genuine Sheepskin Leather
Soft Pigskin Lining
2.16 in Low Kitten Heel
Pointed Toe with Adjustable T-Strap
Available in Black, Apricot and Red, US Sizes 5–12
```

差：

```text
BEST COMFORT: These amazing premium shoes are perfect for every occasion...
women shoes heels pumps wedding shoes comfortable sexy retro vintage
```

- 第一条是 Amazon 式营销长句；第二条是关键词堆砌。

## 关键词规划

若真实排序为：`women's pumps`、`mary jane pumps`、`low heel dress shoes`、`wedding shoes`：

- Title：优先 `mary jane pumps` 与 `low heel`，自然组成标题。
- Key Features：在真实场景要点中使用 `dress shoes`，不重复整段标题。
- Description：若婚礼确为适用场景，自然使用 `wedding shoes`，避免堆砌。
- 若商品事实不能支持某词，记录未覆盖原因，不强行埋入。

## 暂缓词与声明引用

本品只确认是收纳袋，防水能力未知时，`waterproof storage bag` 进入 deferred，晋级条件为用户补充可确认的防水说明；不能先保留进可用词池。确认后补充 fact、运行 rebind、重新确认分类并 export。

若 `key_features.0` 为 `Material: Cotton`，claims 中该片段需引用确认棉材质的事实，不能引用只证明颜色或品类的事实。结构检查能发现引用不存在，是否充分支持声明由语义复核判断。
