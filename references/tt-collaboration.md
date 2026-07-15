# TT 专家共创工作流

用于把 TT / LearnBuddy 中当前可用的专家智能体嵌入山野路迹文创设计流程。这里不是检查表，而是共创流程：本地专家包先参与定义设计方向，脚本再把设计方向落成可导出的文件。

## 核心原则

1. 专家负责设计判断，脚本负责技术实现。
2. 先由本地专家包生成 `output/design_constraints.json` 和 `output/expert_constraints_trace.json`，再改模板、调脚本、导出产物。
3. `output/visual_design_brief.md` 只作为人工阅读摘要，不能作为脚本唯一依据。
4. 每次迭代都记录“专家包来源 -> 专家设计意图 -> 结构化约束字段 -> 用户/Codex 取舍 -> 实际修改”。
5. 不让现有脚本的默认风格绑架产物；当结构化约束与脚本冲突时，优先改脚本或模板。
6. 不编造用户主观信息。团队名、口号、感悟、人名、照片故事仍需用户确认。
7. 不修改专家包文件，不把本机专家包绝对路径写入 skill 或输出约束。

## 当前可用专家

| 专家 | 参与方式 | 对应产物 |
|---|---|---|
| UI 设计师 | 定义整体视觉系统、信息层级、排版比例、组件样式、跨品类统一性。 | 3D 小报、明信片、公众号长图、冰箱贴预览、作品展示页 |
| 小红书运营专家 | 定义九宫格封面钩子、图文顺序、标题、话题、照片选择、传播节奏。 | 小红书社交组图、朋友圈文案、短句和 hashtags |
| Ardot 设计专家 | 定义作品板叙事结构、画板尺寸、节点命名、产物卡片层级和展示动线。 | Ardot / Cocraft 作品板 |
| 现代 Web 开发专家 | 把视觉意图翻译为 HTML/CSS/Canvas/Three.js/STL 可执行约束，处理响应式、性能、截图和参数化。 | 全部脚本、网页、小报、模型和截图导出 |

## 共创顺序

### 1. 定位本地专家包

生成任何文创前，先定位本地专家包根目录：
- 优先使用命令行参数 `--expert-pack-root <dir>`。
- 其次使用环境变量 `SHANYE_EXPERT_PACK_ROOT`。
- 未提供覆盖值时，使用随 skill 分发的 `assets/expert/`。

内置专家包路径由脚本根据 skill 根目录自动解析，不依赖当前工作目录，也不把本机绝对路径写入交付物。

执行：

```text
<PY> scripts/generate_design_constraints_from_experts.py --expert-pack-root "<dir>"
<PY> scripts/validate_design_constraints.py
```

macOS / Linux 如需设置环境变量：

```bash
export SHANYE_EXPERT_PACK_ROOT="<dir>"
python3 scripts/generate_design_constraints_from_experts.py
python3 scripts/validate_design_constraints.py
```

Windows PowerShell 如需设置环境变量：

```powershell
$env:SHANYE_EXPERT_PACK_ROOT="<dir>"
py scripts/generate_design_constraints_from_experts.py
py scripts/validate_design_constraints.py
```

生成脚本只记录专家包 ID、包内相对文件、`trace_id`、短 hash 和证据摘录。不要记录绝对路径。

### 2. 整理输入

准备以下材料给四位专家：
- `references/route_data.json`：距离、日期、海拔、用时。
- `references/matched_photos.json` 和照片缩略图：照片顺序、拍摄位置、可用视觉素材。
- `references/design-system.md`：当前基础风格。
- 已有输出截图：3D 小报、冰箱贴、明信片、公众号、社交组图、Ardot 作品板。
- 用户补充信息：路线名、团队名、口号、感受、禁用内容。

### 3. 让专家先提设计意图

先不要运行或修改脚本。让专家分别输出设计意图：
- UI 设计师：整体视觉关键词、主次层级、字体/颜色/留白/组件建议。
- 小红书运营专家：九宫格第一眼吸引点、九张图的叙事顺序、每张图的标题与信息密度。
- Ardot 设计专家：作品板应该如何让人一眼看懂“输入 -> 设计 -> 产物 -> 迭代”。
- 现代 Web 开发专家：哪些设计可以直接实现，哪些需要参数化、换布局或补截图逻辑。

### 4. 合成结构化设计约束

将专家意见合并为 `output/design_constraints.json`。优先用 `scripts/generate_design_constraints_from_experts.py` 从本地专家包自动推导；手动调整时必须保持来源字段。每个产品都必须包含：

```json
{
  "expert_inputs": {
    "ui": {
      "summary": "UI 设计师原始设计意图",
      "source": {
        "package_id": "UI设计师-agents-design-experience",
        "trace_ids": ["ui:agents/ui-ux-designer.md"],
        "files": ["agents/ui-ux-designer.md"]
      }
    },
    "xiaohongshu": {
      "summary": "小红书运营专家原始设计意图",
      "source": {
        "package_id": "小红书运营专家-xiaohongshu-operations-expert",
        "trace_ids": ["xiaohongshu:agents/xiaohongshu-operations-expert.md"],
        "files": ["agents/xiaohongshu-operations-expert.md"]
      }
    },
    "ardot": {
      "summary": "Ardot 设计专家原始设计意图",
      "source": {
        "package_id": "Ardot设计专家-ardot-design-generator",
        "trace_ids": ["ardot:rules/design-rules.md"],
        "files": ["rules/design-rules.md"]
      }
    },
    "web": {
      "summary": "现代 Web 开发专家可实现性和参数化建议",
      "source": {
        "package_id": "现代Web开发专家-modern-webapp",
        "trace_ids": ["web:rules/instruction.md"],
        "files": ["rules/instruction.md"]
      }
    }
  },
  "composition": {
    "layout": "构图、版式、模型结构或作品板动线",
    "visual_treatment": "会改变产品骨架的视觉处理方式",
    "style_variant": "产品级风格变体，脚本必须读取并改变版式/材质/信息密度",
    "visual_treatment_source": {
      "rationale": "采用这个视觉骨架的专家依据",
      "source": [
        {"role": "ui", "package_id": "UI设计师-agents-design-experience", "trace_ids": ["ui:agents/ui-ux-designer.md"]},
        {"role": "xiaohongshu", "package_id": "小红书运营专家-xiaohongshu-operations-expert", "trace_ids": ["xiaohongshu:agents/xiaohongshu-operations-expert.md"]},
        {"role": "ardot", "package_id": "Ardot设计专家-ardot-design-generator", "trace_ids": ["ardot:rules/design-rules.md"]},
        {"role": "web", "package_id": "现代Web开发专家-modern-webapp", "trace_ids": ["web:rules/instruction.md"]}
      ]
    }
  },
  "visual_differentiators": [
    "相对于脚本默认产物必须出现的视觉差异点"
  ],
  "copy_strategy": {
    "title": "标题、caption、hashtags 或边缘文字策略"
  },
  "script_hooks": {
    "visual_treatment": "脚本必须读取并落地到版式/材质/层级，而不是只写入说明",
    "parameter_name": "脚本必须读取的其他参数"
  },
  "acceptance_checks": [
    "渲染或导出后的产品级验收点"
  ]
}
```

约束写完后运行：

```text
<PY> scripts/generate_design_constraints_from_experts.py
<PY> scripts/validate_design_constraints.py
```

只有校验通过后才能执行各产品生成脚本。校验必须确认：
- `expert_pack.status` 为 `generated_from_local_expert_pack`。
- 四位专家都在每个产品的 `expert_inputs` 中出现。
- 每个 `expert_inputs.<role>.source` 都有 `package_id`、`trace_ids`、`files`。
- 每个产品都有 `composition.visual_treatment_source`。
- 每个产品的 `script_hooks.visual_treatment` 不为空。
- 3D 小报和明信片必须有 `composition.style_variant` 与 `script_hooks.style_variant`，且两者一致。

`visual_treatment` 是强制字段。专家必须把美术判断翻译成可执行处理，例如：
- `field_evidence_card`：小红书采用左侧档案栏、斜切照片、轨迹证据贴片。
- `field_dossier_article`：公众号采用暗色封面档案、测绘数据表、交错照片记录。
- `trail_permit_pass`：明信片采用山野通行证正面和 field log 背面。
- `terrain_control_console`：3D 小报采用暗色测绘台和地形控制台面板。
- `expedition_dashboard`：3D 小报采用硬核探险仪表盘，增加粗粝网格、证据点、强数据面板和更高对比路线。
- `film_ticket`：明信片采用胶片票根和行动凭证感，用胶片孔、虚线票据、暗棕/橙色、照片证据框区别于通行证模板。

如果脚本只改变标题、caption、hashtags，而产品骨架仍像旧模板，视为未执行专家约束。
`style_variant` 必须同时写入 `composition.style_variant` 和 `script_hooks.style_variant`，并由脚本读取后切换 HTML/CSS/Canvas/STL 的实际结构。

### 5. 可选生成人读 brief

从 `output/design_constraints.json` 摘要生成 `output/visual_design_brief.md`。这个文件用于沟通和评审，不用于替代脚本读取。格式：

```md
# 山野路迹视觉设计 Brief

## 总体方向
- 关键词：
- 情绪目标：
- 视觉统一元素：
- 明确不要做：

## 3D 小报
- UI 设计师意图：
- Web 开发落地：
- 需要修改的脚本/模板：

## 冰箱贴
- UI 设计师意图：定义冰箱贴是“可收藏的户外纪念徽章”，不是一块网页截图。必须明确外形、底座外圈宽度、中心浮雕占比、边缘文字位置和可读性；文字应像压印在底座边缘的信息铭牌，不得压到山体上。
- Ardot 设计专家意图：定义模型预览在作品板里的展示角度，确保能看出底座外圈、中心浮雕、轨迹管道和边缘文字四层关系。
- Web/STL 开发落地：
  - 自动判断 GPX 坐标系：对比原始坐标和 GCJ-02→WGS84 转换坐标的 SRTM/GPX 高程吻合度，选择更可信的坐标模式。
  - 底座必须是“外圈 + 中央凹槽”结构，中心顶面掏空，不得与中间地形浮雕重叠。
  - 中心地形浮雕独立封闭，边缘缓坡过渡到凹槽边界；地形不得超出凹槽边界。
  - 边缘文字必须以加粗凹刻方式进入底座外圈，并全部位于中心浮雕边界外；信息字段至少包含路线名、团队名、日期、距离、爬升、用时/最高海拔。
  - 轨迹管道必须细于旧版粗管，默认约 `0.38mm` 半径，贴合地形但不压住山体纹理。
  - 每次导出 STL/OBJ 时保留常规文件和带 `YYYYMMDD_HHMMSS` 时间戳的副本。
  - 生成预览图后做几何验收：地形边界、文字边界、总高度、文件存在性。
- 需要修改的脚本/模板：`scripts/build_magnet_3d.py`、`scripts/render_magnet_preview.py`，必要时同步 `references/ardot-workflow.md` 的交付清单。

## 明信片
- UI 设计师意图：
- Web 开发落地：
- 需要修改的脚本/模板：

## 公众号长图
- UI 设计师意图：
- Web 开发落地：
- 需要修改的脚本/模板：

## 小红书九宫格
- 小红书运营专家意图：
- UI 设计师配合：
- Web 开发落地：
- 需要修改的脚本/模板：

## Ardot 作品板
- Ardot 设计专家意图：
- UI 设计师配合：
- 需要修改的 Ardot 节点/布局：
```

### 6. 脚本落地

按 `output/design_constraints.json` 修改脚本和模板：
- 视觉层：调整 HTML/CSS、字体层级、间距、遮罩、色彩、卡片比例。
- 数据层：继续使用 GPX/EXIF/SRTM 的真实数据，不为视觉效果改造事实。
- 模型层：冰箱贴的外形、地形、轨迹、文字由脚本生成，但美学目标来自结构化约束。
- 截图层：现代 Web 开发专家负责保证不同产物能稳定截图，不出现遮挡、裁切、空白、WebGL 黑屏。

脚本读取规则：
- `scripts/design_constraints.py` 是唯一约束读取入口。
- 小红书组图读取 `social_grid.composition.xhs_grid_plan`、`social_grid.script_hooks.card_plan`、`photo_picks`、`caption_map`、`composition.cover_hook` 和 `copy_strategy.hashtags`。
- 小红书组图还必须读取 `social_grid.script_hooks.visual_treatment` 和每张卡的 `archetype`，并把九张图生成不同视觉骨架，不能共用一个暗色档案模板。
- 公众号读取 `wechat_article.composition.hero_photo`、`script_hooks.photo_sequence`、`copy_strategy.intro_meta`、`hashtags` 和 `visual_treatment`。
- 明信片读取 `postcard.copy_strategy.title_tag`、`title_main`、`title_en`、`back_story` 和 `visual_treatment`。
- 3D 小报读取 `poster_3d.copy_strategy`、`poster_3d.script_hooks.terrain_pad_ratio` 和 `visual_treatment`。
- 明信片和 3D 小报还必须读取 `script_hooks.style_variant`。风格变体要改变构图骨架、信息密度、纹理和照片/数据关系，不能只改变色值。
- 冰箱贴读取 `magnet_3d.copy_strategy.edge_labels`、`magnet_3d.script_hooks.timestamp_exports`、`base_cutout`、`text_outside_relief`。

### 7. 渲染后专家复盘

生成首轮产物后，再让专家基于截图继续参与迭代：
- UI 设计师指出最影响美观和统一性的 3 个改动。
- 小红书运营专家指出九宫格最影响点击/收藏的 3 个改动。
- Ardot 设计专家指出作品板最影响理解和展示的 3 个改动。
- 现代 Web 开发专家指出最值得脚本化、参数化或自动验证的 3 个改动。

## 协同日志模板

将每轮共创追加到 `output/tt_collaboration_log.md`：

```md
# TT 协同日志

## 第 N 轮：专家共创 / 渲染复盘

- 时间：
- 输入材料：
- 专家包来源：

### UI 设计师
- 设计意图：
- 来源 trace_id：
- 写入约束字段：
- 被采纳：
- 落地文件：

### 小红书运营专家
- 设计意图：
- 来源 trace_id：
- 写入约束字段：
- 被采纳：
- 落地文件：

### Ardot 设计专家
- 设计意图：
- 来源 trace_id：
- 写入约束字段：
- 被采纳：
- 落地文件：

### 现代 Web 开发专家
- 技术落地建议：
- 来源 trace_id：
- 写入约束字段：
- 被采纳：
- 落地文件：

### 用户 / Codex 取舍
- 最终决策：
- 未采纳意见及原因：
```

## 发布前复盘模板

生成 `output/final_review.md`。这是设计项目复盘，不是比赛打分表：

```md
# 山野路迹发布前复盘

## 视觉是否更美观
- 统一性：
- 信息层级：
- 情绪表达：
- 最后一轮主要改动：

## 四位专家如何参与设计
- UI 设计师：
- 小红书运营专家：
- Ardot 设计专家：
- 现代 Web 开发专家：

## 脚本承担的技术工作
- 数据解析：
- 模型生成：
- Web/截图：
- Ardot 同步：

## 仍需人工确认
- 主观文案：
- 团队/人物信息：
- 隐私风险：

## 最终结论
- 可发布 / 需继续迭代：
```
