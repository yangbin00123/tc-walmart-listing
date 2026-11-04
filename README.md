# 拓畅-沃尔玛文案生成

独立 Walmart Listing Skill，技术标识 `tc-walmart-listing`，当前版本 **1.0.2**。不依赖网站、网站数据库或部署服务；独立管理版本。

## 功能

本品事实确认 → Sorftime 逐竞品分页扩词 → 完整意图分组 → 可用/暂缓/剔除三类词池 → 写作前词库校验 → Walmart 文案和图片策划 → 覆盖审计与事实、语义、语言质量复核。

保留 Walmart 标题、描述、Key Features 的专用规则。未知属性与歧义词暂缓，不借竞品资料补造本品事实。具体字段与命令见 [SKILL.md](SKILL.md)。

## 环境与安装

需要 Python 3.10+、支持 Skill 的助手，以及已配置认证的 Sorftime MCP（`sorftime-server`）。本地校验脚本仅使用 Python 标准库；认证由使用者自己的 MCP 配置管理，仓库不提供密钥。

### 1. 下载与安装

1. 打开 [最新发布版本](https://github.com/yangbin00123/tc-walmart-listing/releases/latest)，下载 Assets 中的 `tc-walmart-listing-vX.Y.Z.zip` 和 `SHA256SUMS`。优先使用带版本号的安装包。
2. 解压后应得到 `tc-walmart-listing/SKILL.md`，不要多套一层目录。
3. 在 Codex 中，将整个 `tc-walmart-listing` 目录放入用户 Skill 目录：当前官方文档为 `~/.agents/skills/`；使用 `~/.codex/skills/` 的现有环境可保留原安装位置，同名 Skill 只安装一份。Windows 的 `~` 指用户主目录。
4. 新开会话，在 Skill 选择器中查找“拓畅-沃尔玛文案生成”或输入 `$tc-walmart-listing`。未出现时重启宿主并检查目录层级。
5. 先运行 `python3 --version`，确认 Python ≥ 3.10；Windows 可用 `py -3 --version`。更新前备份旧目录，再替换文件，不覆盖个人 MCP 配置。

也可让支持 Skill 安装的助手安装本仓库：

> 请安装 https://github.com/yangbin00123/tc-walmart-listing 中的独立 Skill，保留我的现有 MCP 配置。

### 2. 接入 Sorftime MCP

1. 打开 [Sorftime MCP 服务页面](https://open.sorftime.com/mcp)，登录自己的账号，按后台说明开通 MCP 服务并取得该服务的接入 URL 和密钥。不要混用其他 API/CLI 产品凭证；服务权益及费用以后台为准。
2. 在助手的 MCP 设置中新增远程连接，名称建议 `sorftime-server`，协议选择后台提供的 Streamable HTTP。将后台提供的完整地址及认证信息填写到本机设置；若后台要求 URL 参数认证，按其模板填入自己的密钥。不要把密钥写进本仓库、聊天或反馈截图。
3. Codex 使用配置文件时，在个人 `~/.codex/config.toml` 中添加下面的段落，保留文件其他内容；已有同名连接时更新现有段落，不重复添加：

```toml
[mcp_servers.sorftime-server]
url = "替换为Sorftime后台提供的完整MCP连接URL"
```

这是占位示例，不能原样连接。具体认证方式以 Sorftime 账号后台为准，不自行把查询参数认证换成 Bearer 或 OAuth。其他助手使用各自的 MCP 配置界面，不直接照抄 TOML。

4. 保存后重新连接或重启助手，确认工具列表包含 `walmart_product_traffic_terms`。辅助工具及参数见 [完整接入说明](references/SETUP.md)。若已有可用 Sorftime 连接，直接复用，不必重复安装另一个 Skill 或桥接软件。
5. 先让助手“仅检查 Sorftime 工具是否可发现，不调用扩词或生成”。工具存在不代表额度和认证已验证；正式研究会使用账号额度，收到401/403或额度错误时先按服务后台修正。

接入依据：[Sorftime 服务入口](https://open.sorftime.com/mcp)、[Codex MCP 配置说明](https://developers.openai.com/codex/mcp)、[Codex Skill 安装位置](https://developers.openai.com/codex/skills)。界面名称可能随宿主版本不同。

### 3. 第一次使用

在支持本地文件、Python执行、图片理解和 MCP 的助手中发送：

```text
使用 $tc-walmart-listing 生成美国站沃尔玛文案。
竞品 Product ID：[填入1–20个真实ID]
本品名称：[填写]
本品说明与已确认事实：[数量、尺寸、用途、护理等]
本品参考图：[附上图片]
品牌及授权：[填写或无品牌]
真实变体：[填写或无变体]
暂缓/禁用信息：[填写]
先检查资料是否冲突，词库整理通过后再写文案并完成质量校验。
```

输出为 Markdown、JSON、关键词覆盖报告和完整研究记录；不会自动刊登或写入网站。图片输出是策划文字，不是生成图片。详细资料与规则见 [SETUP.md](references/SETUP.md)。

### 常见问题

- 找不到 Skill：检查 `tc-walmart-listing/SKILL.md` 层级、实际扫描目录和重复安装，重启宿主。
- 找不到 Walmart 工具：检查 Sorftime 连接是否启用、账号权限及宿主是否加载工具；不要用 Amazon 同名工具替代。
- Python 命令不存在：先安装 Python 3.10+，Windows 可把文档命令的 `python3` 改为 `py -3`。
- 只有普通聊天/远程连接、没有文件和Python工具：不能完成本 Skill 的本地校验流程，需换用具备上述能力的宿主。
- 事实不足或歧义词：补充确认资料，或暂缓相关词；不删质量检查来获得通过。

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
