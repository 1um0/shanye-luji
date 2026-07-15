---
name: shanye-luji
description: >
  基于 GPX 轨迹和徒步照片生成山野路迹纪念文创。用于制作或迭代 3D 路迹小报、
  3D 打印冰箱贴 STL/OBJ、路线明信片、公众号长图、小红书社交卡片（3 张或 9 张），以及把这些产物整理到
  Ardot/Cocraft 作品板。适用于徒步、骑行、城市漫步和户外活动纪念；要求先让 TT 专家包生成结构化设计约束，再由脚本落地。
metadata:
  short-description: GPX+照片生成户外纪念文创
---

# 山野路迹

把一条 GPX 路线和一组实拍照片转成可收藏、可分享、可 3D 打印的文创产物。核心原则是：数据真实、专家先定设计、脚本负责复现。

## 何时使用

用户提供或指向以下材料时使用本 skill：
- GPX 路线和徒步/骑行/漫步照片。
- 需要生成 3D 小报、3D 冰箱贴、明信片、公众号长图、小红书社交卡片（3 张或 9 张）。
- 需要根据 UI / 小红书 / Ardot / Web 专家意见迭代视觉。
- 需要把本地产物构建到 Ardot/Cocraft 作品板。

## 必读资料

按任务需要读取，避免一次性加载所有参考：
- 修改整体流程或专家协同时，读 `references/tt-collaboration.md`。
- 修改某个产物或排查视觉/模型问题时，读 `references/product-specs.md`。
- 调整视觉系统时，读 `references/design-system.md`。
- 构建 Ardot/Cocraft 作品板时，读 `references/ardot-workflow.md`。
- 调整结构化约束字段时，读 `references/design_constraints_template.json`。

## 输入规则

必须确认：
- GPX 文件：标准 `.gpx`。
- 照片目录：JPG / HEIC / PNG 均可；HEIC 需要 Pillow + pillow-heif。
- 用户主观信息：路线名、地点/活动名、团队名、slogan、整体情绪、寄语/感悟、小红书风格、话题、天气、不能展示的照片/人物、冰箱贴文字字段。

不要编造团队名、口号、人名、个人感悟、照片故事。用户没有提供时使用中性占位或中性描述。距离、日期、海拔、用时、照片 GPS/时间等客观数据必须来自 GPX/EXIF/SRTM。

累计爬升展示口径固定为最高点减最低点：`max_elevation - min_elevation`。这是为了避免 GPX 海拔抖动让逐点累计爬升失真。

## TT 专家前置

生成任何视觉产物前，先让本地 TT 专家包参与设计，产出机器可读约束，再由脚本读取。默认专家：
- UI 设计师：信息层级、构图、字体、间距、跨品类统一性。
- 小红书运营专家：九宫格叙事、封面钩子、标题、话题、真实记录感。
- Ardot 设计专家：作品板结构、节点命名、展示动线、交付验证。
- 现代 Web 开发专家：HTML/CSS/Canvas/Three.js/STL 可实现性、截图稳定性、参数化。

专家包定位顺序：
1. 命令行参数 `--expert-pack-root <dir>`（显式指定时优先）
2. 环境变量 `SHANYE_EXPERT_PACK_ROOT`
3. 随本 skill 分发的内置专家包：`assets/expert/`

默认情况下无需额外下载或配置专家包。脚本会根据自身位置解析
`<skill-root>/assets/expert/`，因此从任意当前工作目录运行都可以找到内置专家包。
只有在替换或升级专家包时，才需要使用前两种覆盖方式。

不得修改专家包文件。不得把本机专家包绝对路径写入 skill、约束或交付物；只记录 `package_id`、包内相对路径、`trace_id`、短 hash 和证据摘录。

每次生成前必须运行，命令中的 Python 解释器按平台选择：Windows 用 `py` 或 `python`，macOS / Linux 用 `python3` 或已激活虚拟环境中的 `python`。

示例：`<PY> scripts/generate_design_constraints_from_experts.py`，然后 `<PY> scripts/validate_design_constraints.py`。

校验必须通过后才能生成产物。每个产品都应包含：
- `expert_inputs`：四位专家的设计意图和来源。
- `composition.visual_treatment_source`：视觉骨架来自哪些专家依据。
- `composition.style_variant`：产品级风格变体，必须影响版式、材质、信息密度或构图骨架。
- `composition.palette_strategy`：品牌锚点、产品级 palette 和理由。
- `visual_differentiators`：相对脚本默认产物的差异点。
- `copy_strategy`：标题、caption、hashtags、边缘文字等。
- `script_hooks`：脚本实际读取的参数，如 `visual_treatment`、照片顺序、地形外扩、产品级配色、冰箱贴几何规则。
- `acceptance_checks`：产品级验收点。

默认品牌色库只是 fallback，不是固定模板。所有产品必须优先读取 `script_hooks.product_palette`；禁止 3D 小报、明信片、公众号和九宫格全部套同一套深色或松针绿模板。

风格变化必须在生成前完成，不在生成后补说明。`generate_design_constraints_from_experts.py` 应根据用户情绪、照片气质和专家包依据选择 `style_variant`。当前至少支持：
- 3D 小报：`terrain_control_console`、`expedition_dashboard`、`museum_terrain_case`、`photo_journal_terrain`。
- 明信片：`trail_permit_pass`、`film_ticket`、`field_note`、`museum_specimen`。

脚本必须读取 `script_hooks.style_variant` 和 `script_hooks.visual_treatment`。如果只换标题、caption、hashtags 或 palette，而版式骨架仍像旧模板，视为未执行专家约束。
骨架级变化至少要改变主视觉占比、信息面板位置、照片/数据关系中的两项。例如 `film_ticket` 明信片不得继续使用原“左标题右照片”通行证结构，`expedition_dashboard` 3D 小报不得继续使用原“左地形右数据栏”结构。

## 双平台运行规范

本 skill 必须同时兼容 Windows Learn Buddy 和 macOS Codex/终端。除非用户明确要求，不要调用 `.sh` 脚本；统一使用 Python 脚本入口。

Python 命令选择：
- macOS / Linux：优先用 `python3`，若虚拟环境激活后也可用 `python`。
- Windows：优先用 `py` 或 `python`，不要用 `python3` 作为唯一写法。
- 自动化脚本里使用 `sys.executable` 或用户传入的 `--python`、`--image-python`、`--magnet-python`。

路径规则：
- 命令示例一律给引号包裹路径，允许中文目录和空格。
- 脚本内使用 `pathlib.Path` 或 `os.path.join`，不得硬编码 `/Users/...`、`C:\...`、旧测试 GPX 或本机专家包绝对路径。
- 用户传入的 GPX、照片目录、专家包目录必须通过参数或环境变量进入流程。

浏览器与截图：
- 截图只用 `<PY> scripts/screenshot_all.py`。
- 脚本会自动查找 macOS Chrome 和 Windows Chrome，包括 `C:/Program Files/Google/Chrome/Application/chrome.exe`。
- 找不到 Chrome 时提示用户安装或传 `--chrome "<chrome-or-chrome.exe>"`，不要失败后改用 macOS 专属截图命令。

字体与中文 3D 文字：
- 网页字体使用 `scripts/platform_utils.py` 的跨平台 CSS 字体栈。
- 3D 模型中文文字使用 `find_chinese_font()` 查找实体字体：Windows 优先微软雅黑，macOS 优先苹方/冬青黑体，Linux 优先 Noto/思源黑体。
- 冰箱贴中文铭牌必须安装 `mapbox-earcut`；缺失时停止并提示安装，不能静默跳过文字。

依赖策略：
- 首次在新机器上运行，先检查环境，再安装缺失依赖。
- Windows Learn Buddy 若自带 Python 没有第三方包，必须先安装 `requirements.txt`，或通过 `--image-python` / `--magnet-python` 指向已装依赖的 Python。
- HEIC 读取依赖 `Pillow + pillow-heif`；冰箱贴依赖 `numpy + trimesh + shapely + matplotlib + mapbox-earcut`。

## 推荐执行

首次在新机器上运行，先检查环境并安装缺失依赖。

Windows PowerShell：

```powershell
py scripts/check_environment.py
py -m pip install -r requirements.txt
```

macOS / Linux：

```bash
python3 scripts/check_environment.py
python3 -m pip install -r requirements.txt
```

完整生成优先用一键管线。

macOS / Linux 示例：

```bash
python3 scripts/generate_all.py \
  --gpx "<route.gpx>" \
  --images "<image_dir>" \
  --expert-pack-root "<expert_pack_root>" \
  --route-name "<路线名称>" \
  --place-name "<地点/活动名>" \
  --team-name "<团队/组织名>" \
  --mood "<整体情绪>" \
  --xhs-style "<小红书文案风格>" \
  --hashtags "<话题标签>"
```

Windows PowerShell 示例：

```powershell
py scripts/generate_all.py `
  --gpx "<route.gpx>" `
  --images "<image_dir>" `
  --expert-pack-root "<expert_pack_root>" `
  --route-name "<路线名称>" `
  --place-name "<地点/活动名>" `
  --team-name "<团队/组织名>" `
  --mood "<整体情绪>" `
  --xhs-style "<小红书文案风格>" `
  --hashtags "<话题标签>"
```

如果已有 `references/route_data.json`、`references/photos_data.json` 和 `output/photos/`，可复用现有数据：

```text
<PY> scripts/generate_all.py
```

使用外部专家包覆盖内置专家包时：

```text
<PY> scripts/generate_all.py --expert-pack-root "<expert_pack_root>"
```

常用选项：
- `--output-root "<dir>"`：把本次案例的 HTML/PNG/STL/OBJ 输出到独立目录。
- `--references-root "<dir>"`：把本次案例的 route/photo/content/design 中间数据写到独立目录。
- `--shape hexagon`：默认冰箱贴六边形。
- `--shape circle`：用户明确要圆形时使用。
- `--skip-magnet`：只生成网页和平面产物。
- `--skip-screenshots`：只生成 HTML/STL/OBJ，不截图。
- `--chrome`：指定 Chrome/Chrome.exe 路径。
- `--keep-old-output`：不清理可再生旧输出。
- `--image-python`：指定带 Pillow/pillow-heif 的 Python。
- `--magnet-python`：指定带 trimesh/numpy/shapely/matplotlib/mapbox-earcut 的 Python。
- `--skip-env-check`：跳过依赖检查，只在确认环境已配置时使用。

手动分步时按这个顺序，先把 `<PY>` 替换成当前平台的 Python 命令：

```text
<PY> scripts/prepare_content_assets.py --route-name "<路线名称>" --place-name "<地点/活动名>" --team-name "<团队/组织名>"
<PY> scripts/photo_matcher.py
<PY> scripts/generate_design_constraints_from_experts.py
<PY> scripts/validate_design_constraints.py
<PY> scripts/build_photo_markers.py
<PY> scripts/build_trail_poster.py
<PY> scripts/build_postcard.py
<PY> scripts/build_social_grid.py
<PY> scripts/build_wechat_article.py
<PY> scripts/build_magnet_3d.py --shape hexagon
<PY> scripts/validate_magnet_outputs.py --shape hexagon
<PY> scripts/render_magnet_preview.py
<PY> scripts/screenshot_all.py
<PY> scripts/html_to_ardot_plan.py
<PY> scripts/ardot_manifest.py --json
```

## 产物清单

完整交付至少包括：
- `output/design_constraints.json`
- `output/expert_constraints_trace.json`
- `output/tt_collaboration_log.md`
- `output/trail_poster.html`
- `output/trail_poster.png`
- `output/trail_postcard.html`
- `output/trail_postcard.png`
- `output/trail_wechat.html`
- `output/trail_wechat.png`
- `output/social_card_01.html` 到 `output/social_card_0N.html`（卡片数量由 `card_plan` 项数决定，支持 3 张或 9 张）
- `output/social_card_01.png` 到 `output/social_card_0N.png`
- `output/social_grid_preview.html`
- `output/magnet_3d_hexagon.stl`
- `output/magnet_3d_hexagon.obj`
- `output/magnet_3d_hexagon_YYYYMMDD_HHMMSS.stl`
- `output/magnet_3d_hexagon_YYYYMMDD_HHMMSS.obj`
- `output/magnet_3d_latest_timestamp.txt`
- `output/magnet_3d_preview.png`
- `output/magnet_3d_ardot_preview.png`
- `output/ardot_editable_plan.json`
- `output/ardot_manifest.json`

圆形冰箱贴只在用户明确要求时生成对应 `magnet_3d_circle.*`。

## 关键验收

生成后至少检查：
- `<PY> scripts/validate_design_constraints.py` 通过。
- `<PY> scripts/check_environment.py` 无缺失，或已按 `requirements.txt` 安装依赖。
- `output/design_constraints.json` 不含旧字段 `palette_role`，每个产品有 `palette_strategy` 和 `product_palette`。
- 明信片和 3D 小报的 `style_variant` 必须在截图上可见地改变主结构；不能只是换背景色、边框或局部装饰。
- 3D 小报截图不空白，地形边缘封口自然，节点缩略图显示真实照片。节点缩略图必须用内嵌 `thumb`，避免 `file://` WebGL texture CORS 问题；缩略图材质必须启用 `depthTest`，避免穿透山体显示。
- 冰箱贴底座是外圈 + 中央凹槽，中心浮雕不与底座重叠，边缘文字在浮雕外并以加粗凹刻槽呈现，轨迹线细于旧版粗管，STL/OBJ 常规文件和时间戳副本都存在；`<PY> scripts/validate_magnet_outputs.py --shape hexagon` 必须通过。
- 明信片和社交图的轨迹叠加无深色底块，路线颜色在照片上可读。
- 小红书社交卡片来自专家导演表，卡型不重复成同一个暗色模板。卡片数量由 `card_plan` 数组长度控制（通常 3 张或 9 张），3 卡模式推荐 cover_burst / ridge_frame / finish_receipt 覆盖出发-过程-结束叙事节奏。
- 小红书社交卡片不出现"现场照片和路线数据对得上"这类数据证明式文案，轨迹图不显示说明性标题；照片无厚边框，文字层轻透明，团队名以低透明水印呈现。
- 小红书社交卡片的 headline/subline/caption 必须由专家导演表逐张区分，不能多张重复同一句话；不默认渲染"路线说明""节点记录"等内部标签；单张卡不能重复出现两组里程/海拔。
- 公众号长图无文字重叠、图片断裂或截断。
- `output/ardot_manifest.json` 路径指向最新截图和最新时间戳模型。

## Ardot / Cocraft

用户要求在 Ardot/Cocraft 中构建时，先完成本地生成，再读 `references/ardot-workflow.md`。Ardot 不替代本地管线；默认交付必须是可编辑设计文件，不是截图展板。

默认使用 `native_editable_rebuild` 模式：
1. 先运行 `<PY> scripts/html_to_ardot_plan.py --json` 和 `<PY> scripts/ardot_manifest.py --json`。
2. 新建或定位页面 `山野路迹文创可编辑重建`。
3. 按 `output/ardot_editable_plan.json` 从 HTML/约束重建 Ardot 原生节点：文字转 text，色块/卡片转 frame，照片转 image fill，SVG 轨迹/海拔转 SVG frame/vector。
4. 小红书九宫格、明信片、公众号这类平面产物必须以可编辑层为主；PNG 截图只能作为隐藏参考层、对照层或验收截图，不能作为主交付。
5. 小红书九宫格在 Ardot 中必须是 9 个 `1080 × 1080` 可编辑卡片，每张包含可编辑照片 frame、headline/subline/caption/stamp/data text、轨迹 SVG 和水印 text，不得整张贴 PNG。
6. Ardot 画布里不要放解释性标题、说明段落、来源标注、教程文字或“editable/reference”说明；来源和边界写入 `output/ardot_manifest.json`、节点命名或最终回复。
7. 3D 小报的 WebGL 地形、冰箱贴 STL/OBJ 不能从 HTML 直接转成 Ardot 原生 3D；这些区域可用渲染预览作为不可编辑 reference，但右侧数据面板、标题、照片网格、路线信息等仍要重建为可编辑层。
8. CSS filter、blend-mode、backdrop-filter、canvas、Three.js/WebGL、STL/OBJ 都属于有损或不可原生化内容，必须按近似层或预览层处理，不得声称像素无差别。
9. 用 `capture_layout` 和 `capture_screenshot` 检查可编辑节点是否重叠、裁切、挤压；截图只是验收材料，不是交付主体。
10. 最终回复 Ardot 文件链接、页面/画板节点 ID、可编辑边界和验证结果。

只有用户明确要求“像素预览 / 只要视觉完全一致 / 可以接受不可编辑”时，才使用 `pixel_reference_preview` 模式：
1. 新建页面 `山野路迹文创像素参考`。
2. 使用全尺寸 PNG 作为 reference，不作为可编辑最终交付。
3. 页面和最终回复必须明确这是参考预览，不是可编辑版本。

如果 Ardot MCP 不可用或无写权限，明确说明只能交付本地 `output/`。

## 维护规则

- 用 `scripts/design_constraints.py` 作为唯一结构化约束读取入口。
- 用 `scripts/html_to_ardot_plan.py` 作为 HTML 到 Ardot 可编辑重建的唯一计划入口。
- 保持 Windows 与 macOS 双平台兼容：新增命令优先写 Python 入口；新增路径用 `Path`；新增字体、Chrome、截图逻辑走 `platform_utils.py`。
- 修改脚本后运行相关生成命令和截图验证，不只做语法检查。
- 不保留 `v10` 这类版本号脚本；用语义化文件名和时间戳模型文件。
- 不保留旧版本可再生输出，除非用户要求对比。
- 不提交 `.DS_Store`、`__pycache__`、临时调试截图或本机绝对路径。
- 每轮视觉/模型迭代都追加 `output/tt_collaboration_log.md`，记录专家来源、约束字段、用户/Codex 取舍和落地文件。
