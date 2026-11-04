# 拓畅-沃尔玛文案生成

独立 Walmart Listing Skill，技术标识 `tc-walmart-listing`，当前版本 **1.0.1**。不依赖网站、网站数据库或部署服务；独立管理版本。

## 功能

本品事实确认 → Sorftime 逐竞品分页扩词 → 完整意图分组 → 可用/暂缓/剔除三类词池 → 写作前词库校验 → Walmart 文案和图片策划 → 覆盖审计与事实、语义、语言质量复核。

保留 Walmart 标题、描述、Key Features 的专用规则。未知属性与歧义词暂缓，不借竞品资料补造本品事实。具体字段与命令见 [SKILL.md](SKILL.md)。

## 环境与安装

需要 Python 3.10+、支持 Skill 的助手，以及已配置认证的 Sorftime MCP（`sorftime-server`）。本地校验脚本仅使用 Python 标准库；认证由使用者自己的 MCP 配置管理，仓库不提供密钥。

下载 Release ZIP，解压得到 `tc-walmart-listing` 文件夹，放到 `~/.codex/skills/`。更新时先备份原目录，再替换 Skill 文件，保留自己的主机 MCP 配置。

调用 `$tc-walmart-listing`，提供目标国家、1–20 个竞品 Product ID、本品图片和已确认资料。显示名称为“拓畅-沃尔玛文案生成”。

当前能力记录仅核实 Sorftime Walmart 美国站关键词数据；加拿大、墨西哥不可冒用美国数据完成研究。明确要求时可做独立语言测试，不能当作完整关键词验收。

## 验证

```sh
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
```

测试使用离线合成数据，不触发付费生成。真实数据流程还须按 Skill 执行研究、词库检查和最终语义复核；自动测试不替代这些步骤。

## 版本管理

采用独立 SemVer：规则或数据契约的不兼容变化升主版本，兼容能力增加升次版本，兼容修复升补丁版本。每次发布更新 `VERSION` 和 `CHANGELOG.md`，测试通过后创建匹配的 `vX.Y.Z` Git tag 与 GitHub Release，附安装 ZIP 与 SHA-256 校验文件。已发布 tag 不覆盖；修正另发补丁版本。

初始版本来源于已验证的 Walmart Skill 快照，独立打包后不自动更新任何网站调用副本。仓库不包含真实商品资料、任务运行数据或凭证。

完整输入、输出、运行环境与 MCP 接入检查见 [独立使用说明](references/SETUP.md)。
