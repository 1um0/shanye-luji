# Ardot 交付工作流

用于把本地生成的山野路迹文创产物同步到 Ardot/Cocraft。仅在 Ardot MCP 可用时执行；不可用时仍交付 `output/` 本地文件，并明确说明未同步到 Ardot。

## 核心原则

默认交付是 `native_editable_rebuild`：尽量从 HTML/约束重建 Ardot 原生节点，而不是把 PNG 截图贴进画布。

| 模式 | 使用条件 | 可见层要求 |
|---|---|---|
| `native_editable_rebuild` | 默认；用户要求可编辑、能在 Ardot 中修改 | text/frame/image fill/SVG 等 Ardot 原生节点为主 |
| `pixel_reference_preview` | 用户明确只要像素预览，或用于隐藏/对照参考 | 全尺寸 PNG 只能做 reference，不是可编辑主交付 |

平面产物必须优先可编辑：小红书九宫格、明信片、公众号长图都要拆成 text、frame、image fill、SVG 等节点。3D 小报 WebGL 地形和冰箱贴 STL/OBJ 不能原生转为可编辑 3D，可用预览图作为局部 reference，但可编辑的数据面板、标题、照片格、文字层仍应重建。

## 前置产物

先完成本地构建，再进入 Ardot：

```text
<PY> scripts/build_trail_poster.py
<PY> scripts/build_postcard.py
<PY> scripts/build_social_grid.py
<PY> scripts/build_wechat_article.py
<PY> scripts/build_magnet_3d.py --shape hexagon
<PY> scripts/validate_magnet_outputs.py --shape hexagon
<PY> scripts/render_magnet_preview.py
<PY> scripts/html_to_ardot_plan.py --json
<PY> scripts/ardot_manifest.py --json
```

`<PY>` 按平台替换：Windows Learn Buddy 通常用 `py`，macOS / Linux 通常用 `python3`，已激活虚拟环境时也可用 `python`。

## Native Editable Rebuild

1. 读取 `output/ardot_editable_plan.json`；若不存在，运行 `<PY> scripts/html_to_ardot_plan.py --json`。
2. 读取 `output/ardot_manifest.json`；若不存在，运行 `<PY> scripts/ardot_manifest.py --json`。
3. 新建页面 `山野路迹文创可编辑重建`。
4. 每个产品单独顶层 frame；页面里不要放解释性文字、教程、来源标签或文件清单。
5. 小红书九宫格必须重建为 9 张 `1080 × 1080` 可编辑卡片。每张卡至少包括：
   - 照片 frame，使用 `upload_images` 作为 image fill。
   - headline、subline、caption、stamp、data tile、route/place/page、team watermark 等 text 节点。
   - 轨迹 SVG/vector 节点，不加深色底块，不显示说明性标题。
6. 明信片按 front/back 两个可编辑 frame 重建，照片为 image fill，文字和数据为 text，路线/海拔优先重画为 SVG/vector。
7. 公众号长图按 hero、intro、stats、story、photo blocks、elevation、footer 分段 frame 重建，避免一个超高不可控节点。
8. 3D 小报左侧 WebGL 地形可用 `trail_poster.png` 的地形区域做 reference，右侧信息面板、照片网格、标题、路线数据要可编辑。
9. 冰箱贴 STL/OBJ 只能作为本地文件交付；Ardot 中用预览图显示模型效果，并把标题/规格/边缘文字说明等重建为可编辑节点。
10. PNG 截图可以作为隐藏参考层或单独 `像素参考` 页面，但不得覆盖在可编辑主画板上冒充可编辑成果。

## 转换规则

| HTML 内容 | Ardot 处理 |
|---|---|
| 文本、标题、数据、caption | 创建 text 节点，保持可编辑 |
| div 背景、卡片、分割线、贴纸 | 创建 frame/rectangle，近似颜色、透明度、圆角 |
| img / background-image | 创建 frame/rectangle，并用 `upload_images` 作为 image fill |
| SVG 轨迹、海拔剖面 | 用 SVG frame/vector 插入，保持路径可选择 |
| CSS filter / blend-mode / backdrop-filter | 近似为透明色块或叠加层，记录为 lossy_css |
| canvas 图形 | 优先从嵌入 JS/source data 重画为 SVG/vector；不能重画时标为 reference-only |
| Three.js/WebGL 地形 | 不能从 HTML 直接变成 Ardot 原生 3D，只保留局部预览层和可编辑信息层 |
| STL/OBJ 冰箱贴模型 | 不能作为 Ardot 原生 3D 编辑对象；展示渲染预览，模型文件本地交付 |

## 小红书禁用项

Ardot 重建时也必须遵守小红书 HTML 的禁用项：

- 不出现“现场照片和路线数据对得上”“现场照片和路线数据对的上”“路线数据对得上”“证明真的上来了”等数据证明式文案。
- 不出现“此刻在路线上的位置”这类轨迹图说明标题。
- 不渲染“路线说明”“节点记录”等内部卡型标签。
- 不把九张卡做成同一张截图或同一套暗色模板。
- 不让单张卡重复出现两组里程/海拔。

## Ardot MCP 顺序

1. 用 `fetch_file_info` 确认当前文件、`fileId` 和 `readwrite` 权限。
2. 用 `create_new_page` 新建并命名 `山野路迹文创可编辑重建`；页面名必须在创建时传入，内容写入后不要再用 `batch_edit U(<PAGE_ID>, {name: ...})` 更新 PAGE 节点，避免页面子节点丢失。
3. 用 `locate_available_space` 找到可插入区域。
4. 使用 `batch_edit` 分批创建顶层 frame、文字、矢量和图片占位；单次不超过 25 个操作。
5. 每次 `batch_edit` 返回新节点 ID 后，立即用 `batch_read` 读取页面和关键节点，确认节点真实存在且子级数量正确。若读取不到，说明写入没有持久落地；必须换新页面或修正 `parentId` 后重建，不得继续使用返回的幻影 ID。
6. 使用 `upload_images` 把本地照片填充到对应 frame。
7. 用 `batch_read` / `capture_layout(..., problemsOnly:true)` 检查节点尺寸、数量、溢出和重叠；照片底图、半透明遮罩、文字层之间的预期叠放可以接受，文字互相压叠和出框必须修。
8. 用 `capture_screenshot` 抽检单张卡片或局部。截图只用于验收，不是主交付。
9. 最终回复 Ardot 文件链接、页面节点 ID、关键画板节点 ID 和验证结果。

## 验证标准

- 可编辑页中，小红书卡片不是整张 PNG/image fill；每张卡至少有照片 frame、多个 text 节点和 SVG/vector 轨迹节点。
- `batch_read` 能读到最终页面、主九宫格 frame 和 9 个 `1080 × 1080` 卡片；不能只相信 `batch_edit` 的 success 返回。
- 页面没有额外解释性文字、说明段落、来源标签或教程内容。
- 禁用文案和内部标签在 HTML、Ardot text 节点中均不存在。
- 九宫格每张卡是 `1080 × 1080`，3×3 排列时不缩放、不拉伸。
- `capture_layout` 无重叠、裁切和挤压问题，或问题已解释为可接受的 reference 边界。
- 最终回复必须包含 Ardot 文件链接，例如 `cocraft://localhost/file/<fileId>?node_id=<nodeId>`。
