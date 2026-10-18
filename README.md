# txxUI

根据需求文档或原型，结合 Taste 和项目已有设计规范，在 MasterGo 中绘制可编辑的实际 UI 稿。

txxUI 与 [txxprd](https://github.com/mastarai2024-del/txxprd) 配合：txxprd 写清需求，txxUI 将需求落实到指定画布，再把最终画板、截图和未决项交回文档流程。

| 技能 | 负责的交付 |
|---|---|
| txxprd | PRD、业务规则、流程、验收标准、文档配图及附件 |
| txxUI | MasterGo 入口页面、菜单、编辑/确认/反馈状态、素材修复与视觉统一 |

显示名为 **txxUI**，技能标识和调用名为 **txxui / $txxui**。

## 使用

```text
使用 $txxui，把这份 PRD 的页面画到 MasterGo 的“测试尝试”中。
最终设计稿只读，可以复制到目标；保留原稿风格，图片需要独立保存。
```

```text
使用 $txxui，按这张现有 App 菜单调整当前画板，
并检查同组页面里已授权范围内的菜单、弹窗和按钮是否需要统一。
```

可以提供飞书文档、完整导出内容、HTML 原型、截图或 MasterGo 画板。需求缺少关键规则时会指出具体缺口；已明确的目标和授权不重复询问。

## 安装到 Codex

先确认目标目录不存在，再执行：

```bash
git clone https://github.com/mastarai2024-del/txxUI.git "${CODEX_HOME:-$HOME/.codex}/skills/txxui"
```

安装后在能重新发现技能的会话中使用 `$txxui`。已有同名技能时先备份和比较，再决定更新方式。

首次设计、优化或视觉评审时，txxUI 会自动检查 Taste，缺失时安装完整技能目录；已有完整版本直接复用，不覆盖或自动升级。也可以在安装后立即准备依赖：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/txxui/scripts/ensure_taste.py"
```

脚本需要 Python 3。优先复用 Codex、共享 Agent 和 Claude 技能目录下的 `design-taste-frontend` / `taste-skill`；新安装默认进入 Codex 技能目录。来源为 [官方 Taste v2](https://github.com/Leonxlnx/taste-skill/tree/f624f37a8c650b9cc550253104925efe4c8de246/skills/taste-skill)，固定提交，包含 references、scripts、library 和 assets。优先使用本机官方 skill-installer；没有该辅助工具时，用 Python 标准库下载同一固定提交的档案，仅提取目标技能目录，不执行下载内容。安装中断、离线或已有目录不完整时会返回具体错误并保留原目录。

返回的 `skill_file` 可由 Agent 直接读取，本次任务即可使用；新技能在下一轮对话的技能发现列表中可用。`--check-only` 只检查；`--skills-root /path/to/isolated/skills` 仅在指定目录检查和安装，适合隔离验证。

Taste 完整流程原本面向营销网页。txxUI 在 App、后台和已有产品中采用其层级、排版、布局与截图审查方法，配色、字体和按钮形态仍由项目设计规范决定；不会把随机品牌配色、网页图片数量或动画要求套到 App。具体分支见 [Taste 与项目规范](references/taste-integration.md)。

运行 MasterGo 流程需要当前环境可用的 MasterGo MCP，以及已打开、具备相应访问权的目标文件。读取飞书文档需要 txxprd 或其他可用的飞书读取工具；已经提供完整文档内容时不依赖飞书连接。

技能不会自动修改 MCP 配置、升级插件、购买图片或发布应用。具体工具参数和生成后 QA 门禁，以当前 MasterGo server 为准。

## 里面有什么

- [SKILL.md](SKILL.md)：触发条件、分工、执行分支及交付约束。
- [绘制流程](references/workflow.md)：需求拆分、状态清单、原稿基线、逐页绘制及交接。
- [Taste 与项目规范](references/taste-integration.md)：自动依赖准备、项目基线优先、App/营销网页分支与实际画布复核。
- [MasterGo 工具路由](references/mastergo-tools.md)：生成、局部更新、换图、全量同步和异步写入。
- [素材与还原](references/assets-and-fidelity.md)：灰框、实际图层复制、独立副本和复杂区域还原。
- [布局与验收](references/layout-and-review.md)：菜单、表单、底部区域、层级、截图与内容回归。
- [多轮实践复盘](references/lessons.md)：从绘制、修正到 HTML 与文档同步的经过，以及可复用的坑点清单。
- [任务与交接模板](templates/ui-task.md)：项目私有状态记录及 txxprd 交接。

公开复盘已去掉业务文档地址、真实节点、账户、本机路径及原始图片。像素值和页面数量是案例，不是通用设计规范。

## 截图总览工具

`scripts/contact_sheet.py` 只读取本地图片，生成编号总览和 JSON 索引，不连接任何外部服务。需要 Python 3 和 Pillow；可复用已有环境，缺少依赖时在虚拟环境中安装。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install Pillow
.venv/bin/python scripts/contact_sheet.py \
  --output /path/to/private-review/overview.png \
  --columns 4 --thumb-width 320 \
  /path/to/private-review/shots/*.png
```

工具保留原图，缩略图保持比例，序号通过同名 `.json` 文件映射到输入。已有输出默认拒绝覆盖，确需覆盖时加 `--overwrite`。总览只能辅助目检，不能证明画布写入或设计验收通过。

## 验证边界

这份技能来自实际绘制与修正过程。发布前进行了技能格式检查、引用检查、脱敏检查、流程情景走查，以及截图工具测试。整理技能本身没有重新改写业务画布；MasterGo 的版本变化仍需按实际接口检查。

本仓库的主分支是可安装来源。维护时先建独立分支/worktree；工具输出、业务材料、截图、凭证和临时记录不进入 Git。

本地测试：`python3 -m unittest discover -s tests -v`，覆盖截图工具和 Taste 依赖的复用、缺失安装、幂等、失败清理、旧目录保护等分支。行为决策的走查场景见 [evals/scenarios.md](evals/scenarios.md)，需要结合当前工具规则判断，不能当作已执行的画布测试。
