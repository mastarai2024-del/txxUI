---
name: txxui
description: 根据需求或原型，在 MasterGo（莫高）中绘制、修改和核对可编辑界面，复用现有组件与自动布局，并向需求文档交付对应状态的截图。
metadata:
  display_name: txxUI
  source: "https://github.com/mastarai2024-del/txxUI"
---

# txxUI

涉及绘制时交付实际 MasterGo 图层与对应截图。现有项目保留原稿结构、素材和风格，按确认需求做最小增量；需求文档、静态设计与真实应用分别记录状态。

从本次指示与项目记录取得需求、运行版本、设计基线、目标画布和业务规则。已有登记的项目沿工作区项目说明或个人上下文查找入口。字体等个人偏好也从适用的个人上下文取得。项目以运行页面为基线时按[运行页面基线](references/app-baseline.md)核对，历史改稿按[改稿分析与沉淀](references/designer-change-review.md)选择实际可比的稿件。

## 画布按任务与 PRD 归属

从本次指示或项目约定取得可写文件和父页面，按[目标与来源核对](references/workflow.md#3-锁定目的地与来源)定位。同一需求续做优先复用已登记画布。

## 按请求选择最短路径

| 请求 | 路径 |
|---|---|
| 以运行页面为基线的设计、修改或现状评审 | 先读[运行页面基线](references/app-baseline.md)，核对当前页面与本次相关入口；绘制方法仍按下列分支选择 |
| 分析设计师如何改 AI 稿、沉淀经验 | 按[改稿分析与沉淀](references/designer-change-review.md)锁定双方版本，结合原生属性与逐状态图片解释变化；仅维护获准的技能，不据此改设计或产品规则 |
| 修改现有页面、补开关或入口 | `get_selection_node` 读精确目标，保留未改属性，用 `agent_update_node` 做局部增量 |
| 组件复用、状态调整或明确要求组件化/母版联动 | 按[组件外观与实例](references/components-and-instances.md)选真实样板，分清内容、状态和传播范围；创建母版仍须明确需求 |
| 整理自动布局、长内容或换实例后的尺寸问题 | 按[自动布局](references/auto-layout.md)处理语义容器及固定/撑开/填充，验证实际内容变化，保留现有视觉与小改范围 |
| 菜单归类或调整层级 | 先核对[旧入口到新路径的映射](references/workflow.md#菜单归类与入口迁移)，再修改首页、二级页与返回路径 |
| 增加或修改折叠区 | 核对[折叠摘要与展开状态](references/layout-and-review.md#折叠摘要与展开状态)，按当前确认覆盖实际状态 |
| 紧凑列表、组摘要或备注状态调整 | 读[紧凑列表与状态可读性](references/layout-and-review.md#紧凑列表与状态可读性)，区分后台关联与可见内容，检查长标题、热区及行内展开 |
| 页面新增小操作或媒体加载状态 | 核对[操作位置与图标含义](references/layout-and-review.md#新增操作的位置与含义)及[媒体状态](references/workflow.md#媒体准备与可操作状态)，保留其他需求已占用的区域 |
| 原稿复制、补已有状态或修复缺图 | 读来源与目标，原生复制完整图层；换图用 `agent_replace_node`，见 [素材与还原](references/assets-and-fidelity.md) |
| 仅修改现成位图的一处，其他像素与尺寸须不变 | 按[局部位图的严格保持](references/assets-and-fidelity.md#局部位图的严格保持)锁定原文件和允许区域，核验实际交付文件；不据此修改设计源 |
| 设计全新页面 | 第一个 MasterGo 动作为 `design_page`，后续按当前返回准备并逐页提交；在允许阶段核对指定父页面 |
| 已有本地文件全量覆盖画布 | 按 `agent_sync_design` 的当前校验与确认要求，不把局部修正升级为全量覆盖 |
| 为 PRD 中的规则制作对照图 | 按[同一组输入的状态对照](references/layout-and-review.md#同一组输入的状态对照)绘制示意图，以已确认规则和实际文档列宽验收 |
| 读取最新设计或回贴 PRD | 按实际内容与已确认范围匹配最终状态，只读导出原生图；缺图单列，不另生成 HTML |
| 指标帮助或多方向弹窗 | 按[指标说明与横竖屏](references/layout-and-review.md#指标说明与横竖屏)验证字段对应关系或各方向下的按钮结果 |
| 只评审或给建议 | 读取与反馈；不据此改图 |

以当前 MasterGo 工具规则为准，详见 [工具路由与异步写入](references/mastergo-tools.md)。只有用户要求前端代码或交互 HTML 时才走代码导出/原型流程。

分阶段交付按[来源与确认范围](references/workflow.md#1-分清输入分别决定什么)核对当前授权。先调 HTML 的任务见[先原型再同步](references/workflow.md#先原型再同步)。

## 字体统一规则

绘制与修改时，字体优先取本次指示、项目已确认规范及已登记的个人偏好。没有约定时，继承认可稿中同角色文字的实际样式。只读导出保留来源外观。

- **先确认可用字体。** 在当前工具允许的阶段用 `get_fonts` 核对可用字重、精确 family 和查询范围。若查询只覆盖团队或企业字体，再从原生字体界面和现有文本节点核实本地或云字体。不可用或发生回退时记录差异。
- **混排按文字片段设置。** 规范对不同文字角色指定字体时，优先保留可编辑文本及片段样式。工具不支持片段样式时，仅拆分必要文字节点并核对基线、间距与换行。标点随所在语段，图标保留原图标资源。
- **节点与截图分别验收。** 回读实际文字节点/片段的 family 与字重，再看最终画布截图，核对缺字、字体回退、混排基线、换行与裁切；字号、行高和字重角色沿用项目规范，以实际可用字重为准。

## 设计依据与执行

1. **固定视觉基线。** 每次绘制或改稿前打开项目登记的设计规范。登记了多套规范时，逐套核对本次涉及的样式、组件和交互状态，按项目已确认的适用范围取用。再按[设计师风格](references/designer-style.md)从认可稿或同模块状态提取同角色属性。当前确认决定增量，续做只重查受到影响且有变化的来源。
2. **按需使用 Taste。** 涉及新布局、样式决策或视觉评审时按[项目适配](references/taste-integration.md)准备并读取依赖。
3. **列出影响。** 按[页面与状态清单](references/workflow.md#2-建立页面与状态清单)核对入口、触发条件、结果与返回，记录受影响状态及引用。文案按[操作需要](references/layout-and-review.md#操作文案按决策需要出现)交代后果。
4. **最小范围绘制。** 按用户指向定位节点，以最新快照修改获准属性。共享组件的变更先核对[引用范围](references/assets-and-fidelity.md#共享关系与修改范围)。按[组件与实例](references/components-and-instances.md)复用原生样板，按[自动布局](references/auto-layout.md)核对实际内容伸缩。
5. **有界提交与核验。** 新页逐页提交，局部改动小批处理。按[工具规则](references/mastergo-tools.md#区分提交结果)区分已受理、未知和实际写入。允许检查时[回读结构并逐页核对视觉](references/layout-and-review.md#验收顺序)。**工具要求停止或等待 QA 确认时，停在当前阶段。**

## 交给文档的内容

任务包含 PRD 更新时，配合 `txxprd`；飞书读取使用其 `lark-cli --as user` 路径，不用 WebFetch。只读设计请求不自动写回文档。

按[完稿与交接](references/workflow.md#7-完稿与交接)记录设计、原型、文档及实际系统的验证结果。发生视觉修改时按[前后配对](references/layout-and-review.md#修改前后配对)留图。小改简要给出目标、改动和验证边界，跨阶段任务填入[现有任务记录](templates/ui-task.md)。

## 按需参考

- [运行页面基线](references/app-baseline.md)：以运行页作基线时从实际入口进入；区分交互手机、导航图与源码，按版本复用组件和入口，记录缺口与验收边界。
- 项目视觉画像按项目名、模块和观测日期在项目记录中查找，复用前核对当前版本。
- [设计师风格](references/designer-style.md)：选最终稿、成对比较、提取角色属性、复用组件与同尺寸验收。
- [组件外观与实例](references/components-and-instances.md)：真实样板、视觉细节、变体/属性、嵌套复用、迁移与继承，按任务加载。
- [自动布局](references/auto-layout.md)：语义容器、尺寸伸缩、动态混排、长内容与滚动/安全区，局部任务只读相关部分。
- [改稿分析与沉淀](references/designer-change-review.md)：还原版本关系，区分实际差异、设计解释、保留项与疑点，将方法和模块案例分别维护。
- [绘制流程](references/workflow.md)：复杂状态、画布层级和完整交接。
- [素材与还原](references/assets-and-fidelity.md)：灰框、复制、图片与实例独立性。
- [布局与验收](references/layout-and-review.md)：菜单、表单、位置和视觉回归。
- [工具路由](references/mastergo-tools.md)：更新、替换、提交与未知状态对账。
- [Taste 适配](references/taste-integration.md)：依赖及 App/网页分支。
- [行为回归请求](evals/requests.md)：维护时在隔离输入上试跑，并按[走查情景](evals/scenarios.md)核对实际行为。
