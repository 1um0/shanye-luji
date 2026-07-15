# 山野路迹产物规格

本文件记录各类文创的可执行规格。`SKILL.md` 只保留调度规则；需要修改某个产物或排查生成问题时再读取本文件。

## 共同规则

- 数据事实只来自 `references/route_data.json`、`references/photos_data.json`、`references/matched_photos.json`、SRTM 采样和用户确认信息。
- 累计爬升展示口径为最高点减最低点：`max_elevation - min_elevation`，避免逐点海拔抖动放大。
- 每个产品先读取 `output/design_constraints.json` 中自己的 `composition.palette_strategy` 和 `script_hooks.product_palette`，默认品牌色只能作为 fallback。
- 3D 小报、明信片等平面/网页产物必须读取 `composition.style_variant` 和 `script_hooks.style_variant`，用它切换版式骨架、材质语言、信息密度和构图；不能只换色。骨架级变化至少要改变主视觉占比、信息面板位置、照片/数据关系中的两项。
- 照片上的轨迹叠加必须透明无底块，路线颜色按照片明暗切换浅/深线，并用 halo 保证可读。
- 新机器先运行 `<PY> scripts/check_environment.py`；缺包时用 `<PY> -m pip install -r requirements.txt`。Windows 的 `<PY>` 通常是 `py`，macOS / Linux 通常是 `python3`。
- 截图使用 `scripts/screenshot_all.py` 自动查找 Chrome。Windows 默认查找 `C:/Program Files/Google/Chrome/Application/chrome.exe`，也可传 `--chrome`。
- 中文字体通过 `scripts/platform_utils.py` 查找，Windows 优先微软雅黑，macOS 优先苹方/冬青黑体，Linux 优先 Noto/思源黑体。
- 生成后必须用真实浏览器截图或模型预览检查，不只看脚本日志。

## 3D 小报

脚本：`scripts/build_trail_poster.py`

输出：
- `output/trail_poster.html`
- `output/trail_poster.png`
- `output/build_data.json`
- `references/srtm_elevation_wgs84.json`

规格：
- 自包含处理 GCJ-02 到 WGS84、SRTM HGT 采样、照片标记清洗、Three.js 3D 场景和右侧数据面板。
- 地形先按路线边界外扩采样，再封闭边缘，避免矩形硬切和空洞边。
- 从 `poster_3d.script_hooks.terrain_pad_ratio` 读取外扩比例；默认约 `0.28`。
- 从 `poster_3d.script_hooks.product_palette` 读取背景、面板、地形低/高色、边缘色、路线金色和强调色。
- 从 `poster_3d.script_hooks.style_variant` 读取小报风格。`terrain_control_console` 为测绘控制台；`expedition_dashboard` 为硬核探险仪表盘，应改为全屏地形主视觉 + 底部悬浮仪表盘，增加粗粝网格、证据感标签、更高信息密度和更强路线强调，不得继续沿用左地形右数据栏。
- 轨迹使用 `TubeGeometry`，高度贴合地形表面，速度数据来自 `references/route_data.json` 的 `track_points[].speed`；若缺失则按相邻点时间和累计距离估算。
- 节点缩略图必须内嵌小尺寸 `data:image/jpeg;base64,...` 到 `thumb` 字段，Three.js `TextureLoader` 使用 `m.thumb || m.photo`。这是为了避免 `file://` 打开时 WebGL texture 被 Chrome CORS 策略拦截；右侧照片栏和 lightbox 仍使用原始 `photos/*.jpg`。
- 3D 节点照片材质必须启用 `depthTest`，只做轻微离地偏移，避免缩略图穿透地形显示。
- 输出 HTML 应能用 `file://` 直接打开，截图脚本用 Chrome headless + SwiftShader 渲染。

验收：
- 地形非空，边缘已封口且过渡自然。
- 右侧信息面板不遮挡地形主体。
- 3D 节点缩略图显示真实照片，不是空相框。
- Chrome 日志不出现 `origin 'null' has been blocked by CORS policy` 的照片纹理报错。

## 3D 冰箱贴

脚本：
- `scripts/build_magnet_3d.py`
- `scripts/render_magnet_preview.py`
- `scripts/validate_magnet_outputs.py`

输出：
- `output/magnet_3d_hexagon.stl`
- `output/magnet_3d_hexagon.obj`
- `output/magnet_3d_hexagon_YYYYMMDD_HHMMSS.stl`
- `output/magnet_3d_hexagon_YYYYMMDD_HHMMSS.obj`
- `output/magnet_3d_latest_timestamp.txt`
- `output/magnet_3d_preview.png`
- `output/magnet_3d_ardot_preview.png`

规格：
- 默认生成六边形；只有用户明确要求时才生成圆形。
- 自动判断坐标系：对比原始 GPX 坐标与 GCJ-02 转 WGS84 后的 SRTM/GPX 高程吻合度，选择更可信模式。
- 底座是外圈 + 中央凹槽，不是整块实心顶面。中心地形浮雕独立封闭，填住凹槽，避免底座与山体重叠。
- 地形先获取比最终轮廓大一圈的 SRTM 地形，再按圆形/六边形裁切。
- 中央浮雕边缘做缓坡过渡到底座凹槽肩部，不做尖锐硬切。
- 轨迹管道贴合地形表面，默认半径约 `0.38mm`，可通过 `magnet_3d.script_hooks.trail_tube_radius_mm` 调整，避免轨迹线过粗压住山体。
- 文字位于底座外圈，字段优先为路线名、团队名、日期、距离、爬升、用时/最高海拔，不得与山体浮雕重叠。
- 外圈文字默认使用凹刻而非凸起：脚本通过 2D 字形差集生成顶层底座洞口，下层底座露出形成约 `0.85mm` 深的凹槽；字形加粗默认 `0.12mm`，方便切片和打印。
- 中文凹刻文字依赖 `mapbox-earcut` 完成字体轮廓三角化；缺失时必须提示安装，不能静默跳过文字。
- 模型字体用 `platform_utils.find_chinese_font()`，Windows 优先微软雅黑。
- 预览色读取 `magnet_3d.script_hooks.product_palette`，模型本体保持可 3D 打印几何输出。
- 预览脚本只过滤真正的 z=0 底面，不得过滤 z=BASE_HEIGHT 的底座顶面，否则会误判“底座没生成”。

验收：
- STL/OBJ 常规文件和时间戳副本同时存在。
- `<PY> scripts/validate_magnet_outputs.py --shape hexagon` 通过。
- 中心浮雕不与底座实体顶面重叠。
- 文字全部位于中心浮雕边界之外，并以可打印凹刻槽呈现。
- 轨迹线细于旧版粗管，默认不超过 `0.8mm` 直径。
- 预览中能看出底座外圈、中心浮雕、轨迹管道和边缘文字四层关系。

## 明信片

脚本：`scripts/build_postcard.py`

输出：
- `output/trail_postcard.html`
- `output/trail_postcard.png`

规格：
- 正面为山野通行证：暗色底、路线标题、日期、数据格、斜切照片和透明轨迹叠加。
- 背面为 field log：故事、海拔剖面、路线数据和留白区。
- 从 `postcard.copy_strategy` 读取标题、英文副标题和背面故事。
- 从 `postcard.script_hooks.product_palette` 读取正反面背景、文字、印章、轨迹浅/深线色。
- 从 `postcard.script_hooks.style_variant` 读取明信片风格。`trail_permit_pass` 为山野通行证；`film_ticket` 为胶片票根，必须使用独立 HTML 骨架：满版照片主视觉 + 右侧票根 stub + 胶片孔/票据纹理 + 地图窗口，不得继续沿用左标题右照片的通行证结构。
- 轨迹图透明叠在照片上，不允许黑色或深色矩形底。

验收：
- 标题不遮挡照片主体。
- 背面故事不编造用户未提供的主观内容。
- 轨迹在明暗照片上都清晰可见。

## 小红书九宫格

脚本：`scripts/build_social_grid.py`

输出：
- `output/social_card_01.html` 到 `output/social_card_09.html`
- `output/social_card_01.png` 到 `output/social_card_09.png`
- `output/social_grid_preview.html`

规格：
- 小红书专家先输出结构化九宫格导演表：`social_grid.composition.xhs_grid_plan` 和 `social_grid.script_hooks.card_plan`。
- 每张卡至少包含 `photo`、`caption`、`archetype`、`headline`、`subline`、`sticker`、`data_focus`，并可用 `show_data`、`show_role`、`footer_text`、`layout_note` 控制可见信息。
- 九张图必须使用不同卡型，不得套同一个暗色档案模板。
- 常见卡型：封面钩子、路线小票、第一尖记录、狼狈现场、回望分屏、山脊大片、最高点证明、终点复盘。
- 小红书专家应为九张卡分别给出叙事任务和可见文案。禁止多张卡重复同一句 `subline`；“硬核、狼狈但开心”等整体情绪只在封面或收尾集中出现，不得每张都作为底部口号。
- `photo_role` 只在确有必要时显示，默认 `show_role=false`，不要把“路线说明”“节点记录”这类内部卡型标签渲染到画面上。
- 每张卡只保留一组数据锚点；当 caption 已含里程/海拔时，数据块应隐藏或只显示其中一个，不得同屏出现两组里程和海拔。
- 轨迹图为真实 GPS 墨卡托投影 SVG，无背景，标注当前照片位置，但不显示“此刻在路线上的位置”这类说明性标题。
- 从 `social_grid.script_hooks.product_palette` 读取纸面、墨色、票据色、贴纸色和轨迹浅/深线色。
- 不得出现“现场照片和路线数据对得上”“路线数据对得上”“证明真的上来了”这类数据证明式或幕后判断文案。
- 照片优先满幅呈现，不加相纸白边或厚边框；路线名、日期、页码等元信息以小号轻透明叠加。
- 文字内容区使用半透明叠层和轻模糊，透明度由 `script_hooks.text_scrim_opacity` / `data_scrim_opacity` 控制，避免压住照片主体。
- 团队/组织名称不做显眼署名，默认作为低透明水印，透明度由 `script_hooks.team_watermark_opacity` 控制。

验收：
- 九张图顺序来自约束文件。
- 每张 caption 和 archetype 来自专家导演表。
- 每张只显示当前照片或该卡意图需要的数据，不无脑堆全局统计。
- 九张图的 headline/subline/caption 具有不同表达，不出现 3 张以上重复可见短句。
- 不出现“路线说明”“节点记录”等内部卡型标签，除非专家约束显式要求 `show_role=true`。
- 单张卡不重复展示两组里程和海拔。
- 轨迹无深色底块，复杂照片上仍能看见线和定位点。
- HTML/截图中不含禁用文案和轨迹说明标题。
- 照片无边框，团队名为水印化处理，不喧宾夺主。

## 公众号长图

脚本：`scripts/build_wechat_article.py`

输出：
- `output/trail_wechat.html`
- `output/trail_wechat.png`

规格：
- 单栏长图，结构为封面、引导语、数据、故事、配图、海拔剖面、复盘、页脚。
- 从 `wechat_article.composition.hero_photo` 和 `script_hooks.photo_sequence` 读取封面与配图顺序。
- 从 `wechat_article.copy_strategy` 读取 intro meta、hashtags 和复盘策略。
- 从 `wechat_article.script_hooks.product_palette` 读取页面背景、纸面、正文、弱化文字、规则线和警示色。

验收：
- 不像网页后台截图，应该是可阅读的行后复盘档案。
- 数据全部来自 GPX/SRTM/EXIF。
- 长图截图无文字重叠、无图片断裂。

## Ardot 作品板

参考：`references/ardot-workflow.md`

规格：
- Ardot 是交付和策展层，不替代本地生成管线。
- 先运行 `scripts/ardot_manifest.py --json`，再根据 manifest 创建作品板。
- 每个产品单独画板或卡片，体现“输入材料 -> 专家约束 -> 生成产物 -> 迭代记录”。
- STL/OBJ 不能直接嵌入画板，用冰箱贴预览承载视觉，并在文件清单列出常规模型和时间戳模型。

验收：
- 作品板中能看到 3D 小报、明信片、冰箱贴、公众号预览、九宫格和文件清单。
- 布局检查无重叠、裁切和挤压。
- 最终回复包含 Ardot 文件链接、页面/主画板节点 ID 和预览截图路径。
