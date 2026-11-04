# 写作前词库整理

先完成所有竞品研究和事实画像，运行 prepare，读取 03_keyword_view.tsv。它按原始顺序展示全部词及竞品命中数；命中数不是搜索量，不伪造热度。保留原始记录、数字、否定、单位及词序。

按完整搜索意图分组，不按词片段机械分组。先识别商品身份、修饰属性、用途、主观审美和潜在品牌意图，再与本品已确认事实逐项对照。同一种未确认的修饰意图，应跨不同中心词检查一致性；同含某个单词不意味着完整意图一定相同。有合理差异时解释，不能仅因出现厨房或茶巾就把整句话判为可用。

03_keyword_groups.json 格式：{"groups":{"组ID":{"keywords":["准确原词"],"decision":"eligible/deferred/excluded","reason_code":"具体原因代码","reason":"中文原因","query_intent":"完整意图","evidence":"依据及仍存在的疑点","role":"identity/synonym/attribute/intent/broad","fact_ids":["f1"],"relevance":"relevant","intent":"用途或身份","promotion_condition":"暂缓词所需证据"}},"overrides":{}}

每个原词恰好属于一组。组内例外在 overrides 以完整关键词为键，填写不同字段及 group_difference；若产生不同分类或标签，同组各成员均需说明差异（可在组中填写通用差异说明，例外中具体解释）。分组只是统一判断依据，每个词仍保留独立记录。不要用白名单或子串正则批量删词，不设保留率。

- eligible：完整意图有确认事实支持；属性词不能只引用产品身份。
- deferred：品牌、材质、审美定位或用途尚有歧义；记录解除歧义所需证据。用户要求暂缓的词保持隔离。缺证据不等于事实已证伪。
- excluded：明确不匹配、明确他人品牌或真实事实冲突；写具体原因。
- identity/synonym/broad 只用 relevant。high 只用于确有已确认属性或场景缩小搜索范围的 attribute/intent，额外填写 specific_fact_ids，必须属于 fact_ids。热度不决定相关性。
- 不清楚的词可以暂缓，只要还有足够合格词就继续，不要求用户解释所有竞品搜索词。没有合格核心词才停止。

依次执行 quality.py apply-groups RUN、export RUN、check-keywords RUN。检查不通过先修分组与依据，禁止先写07文案。通过后仅用 eligible 安排05，再按沃尔玛规则写07。not_planned 只是可用词未安排，不能代替 deferred 隔离。

脚本检查完整性、引用、同组差异和标签边界，不证明语义判断正确。写作前必须再通读整批分类，重点比较相同修饰意图在不同词中的判断。最终独立语义复审、覆盖检查及原生验收仍必须执行。不得通过伪造分组、引用或差异说明绕过检查。
