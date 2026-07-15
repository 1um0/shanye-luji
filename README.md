# 山野路迹 Skill

基于 GPX 轨迹和徒步照片，自动生成可分享、可收藏、可打印的户外活动纪念文创。

## 能做什么

- 解析 GPX 路线、距离、时间和海拔数据。
- 读取 JPG、PNG、HEIC 照片及 EXIF 信息，并将照片匹配到路线节点。
- 生成 3D 路迹小报、路线明信片、公众号长图和小红书 3/9 宫格卡片。
- 生成六边形或圆形 3D 打印冰箱贴 STL/OBJ 模型。
- 生成 Ardot/Cocraft 作品板结构、预览图和交付清单。

## 目录结构

```text
shanye-luji/
├── SKILL.md
├── README.md
├── requirements.txt
├── scripts/                 # 数据处理、生成、渲染和校验脚本
├── references/              # 模板、路线/照片中间数据和设计约束
├── assets/expert/            # 随 skill 分发的本地专家包
└── output/                  # 生成结果，首次运行时自动创建
```

## 安装

需要 Python 3.10 或更高版本。建议在 skill 目录创建虚拟环境：

### macOS / Linux

```bash
cd /path/to/shanye-luji
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/check_environment.py
```

### Windows PowerShell

```powershell
cd "C:\path\to\shanye-luji"
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py scripts/check_environment.py
```

如果需要读取 HEIC，必须包含 `Pillow` 和 `pillow-heif`。生成冰箱贴需要 `numpy`、`trimesh`、`shapely`、`matplotlib` 和 `mapbox-earcut`。

## 在 Codex 中安装

### 方式一：克隆到本地后使用

```bash
git clone https://github.com/1um0/shanye-luji.git
cd shanye-luji
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

将 `shanye-luji` 目录放入 Codex 可读取的 skills 目录，或在 Codex 中打开该目录并让它读取 `SKILL.md`。内置专家包已经包含在 `assets/expert/` 中，不需要额外下载。

### 方式二：直接下载仓库压缩包

在 GitHub 仓库页面选择 `Code` > `Download ZIP`，解压后进入 `shanye-luji` 目录，按照上面的 Python 依赖安装命令执行即可。

安装完成后，可以在 Codex 中提出类似请求：

```text
使用 shanye-luji，根据 route.gpx 和 photos/ 生成徒步纪念文创。
路线名称：某某山
地点名称：某某景区
```

Codex 会读取 `SKILL.md`，并调用 `scripts/generate_all.py` 完成生成。也可以直接在终端执行“快速开始”中的命令。

## 在 Claude Code 中安装

### 安装目录

如果当前 Claude Code 环境支持项目级或用户级 skills 目录，可以将仓库克隆到对应目录：

```bash
# 项目级安装：只对当前项目生效
mkdir -p .claude/skills
git clone https://github.com/1um0/shanye-luji.git .claude/skills/shanye-luji

# 或用户级安装：对当前用户的多个项目生效
mkdir -p ~/.claude/skills
git clone https://github.com/1um0/shanye-luji.git ~/.claude/skills/shanye-luji
```

然后安装 Python 依赖：

```bash
cd .claude/skills/shanye-luji
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/check_environment.py
```

在 Claude Code 中可以明确指定使用该 skill：

```text
请使用 shanye-luji skill，根据 route.gpx 和 photos/ 生成徒步纪念文创。
```

### 兼容性说明

Claude Code 的调用方式、skills 目录约定和本地工具权限可能因版本或配置不同而变化。本 skill 当前主要在 Codex 环境中设计和验证，Claude Code 版本尚未完成完整调试，以上安装方式属于兼容性尝试，实际调用效果不一定理想。尤其是本地专家包的自动读取、浏览器截图、3D 模型预览和 Ardot/Cocraft 作品板交付，可能需要手动执行脚本或调整路径。

如果 Claude Code 没有自动识别该 skill，可以直接进入 skill 目录，手动执行“快速开始”中的 Python 命令；如果找不到内置专家包，可以显式传入：

```bash
python3 scripts/generate_all.py \
  --gpx "/path/to/route.gpx" \
  --images "/path/to/photos" \
  --expert-pack-root "$(pwd)/assets/expert" \
  --route-name "路线名称" \
  --place-name "地点名称"
```

## 输入要求

至少准备：

- 一个标准 `.gpx` 文件；
- 一个包含 JPG、PNG 或 HEIC 照片的目录；
- 路线名称和地点名称。

可选信息包括队伍名称、slogan、整体情绪、小红书文案风格、话题标签、徒步故事、复盘文字和不允许展示的照片/人物。没有提供的信息不会被虚构，脚本会使用中性描述。

## 快速开始

在 `shanye-luji` 目录执行：

```bash
python3 scripts/generate_all.py \
  --gpx "/path/to/route.gpx" \
  --images "/path/to/photos" \
  --route-name "路线名称" \
  --place-name "地点名称"
```

Windows PowerShell：

```powershell
py scripts/generate_all.py `
  --gpx "C:\path\to\route.gpx" `
  --images "C:\path\to\photos" `
  --route-name "路线名称" `
  --place-name "地点名称"
```

内置专家包位于 `assets/expert/`，默认会自动加载，无需手动设置路径。生成流程会先读取 UI、小红书运营、Ardot 和现代 Web 四类专家约束，再生成设计约束并校验，最后导出各类产物。

## 使用外部专家包

如果要替换内置专家包，可通过参数或环境变量指定新的专家包根目录：

```bash
python3 scripts/generate_all.py \
  --gpx "/path/to/route.gpx" \
  --images "/path/to/photos" \
  --expert-pack-root "/path/to/expert-pack-root" \
  --route-name "路线名称" \
  --place-name "地点名称"
```

也可以设置 `SHANYE_EXPERT_PACK_ROOT`。优先级为：命令行参数、环境变量、内置 `assets/expert/`。

## 常用参数

- `--output-root "目录"`：指定本次输出目录。
- `--references-root "目录"`：指定中间数据目录。
- `--shape hexagon|circle`：选择冰箱贴形状，默认 `hexagon`。
- `--skip-magnet`：跳过 3D 冰箱贴生成。
- `--skip-screenshots`：跳过 Chrome 截图。
- `--chrome "Chrome路径"`：手动指定 Chrome/Chrome.exe。
- `--keep-old-output`：保留输出目录中的旧文件。
- `--image-python "Python路径"`：指定带图像依赖的 Python。
- `--magnet-python "Python路径"`：指定带 3D 建模依赖的 Python。

## 分步运行

需要单独调试某个环节时，可按以下顺序执行：

```bash
python3 scripts/prepare_content_assets.py --route-name "路线名称" --place-name "地点名称"
python3 scripts/photo_matcher.py
python3 scripts/generate_design_constraints_from_experts.py
python3 scripts/validate_design_constraints.py
python3 scripts/build_photo_markers.py
python3 scripts/build_trail_poster.py
python3 scripts/build_postcard.py
python3 scripts/build_social_grid.py
python3 scripts/build_wechat_article.py
python3 scripts/build_magnet_3d.py --shape hexagon
python3 scripts/validate_magnet_outputs.py --shape hexagon
python3 scripts/render_magnet_preview.py
python3 scripts/screenshot_all.py
python3 scripts/html_to_ardot_plan.py --json
python3 scripts/ardot_manifest.py --json
```

## 输出结果

结果默认写入 `output/`，主要包括：

- `trail_poster.html/png`：3D 路迹小报；
- `trail_postcard.html/png`：路线明信片；
- `trail_wechat.html/png`：公众号长图；
- `social_card_*.html/png` 和 `social_grid_preview.html`：社交卡片；
- `magnet_3d_*.stl/obj`：3D 打印模型及预览；
- `design_constraints.json`：结构化设计约束；
- `expert_constraints_trace.json`：专家来源、相对文件路径、hash 和证据摘录；
- `ardot_editable_plan.json`、`ardot_manifest.json`：作品板结构与交付清单。

## 常见问题

### 找不到专家包

确认 `assets/expert/` 仍在 skill 目录中。若使用外部专家包，检查 `--expert-pack-root` 或 `SHANYE_EXPERT_PACK_ROOT` 指向包含四类专家子目录的根目录。

### 找不到 Chrome

安装 Google Chrome，或使用 `--chrome` 指定可执行文件路径。缺少 Chrome 时仍可生成 HTML、图片以外的其他产物，但截图步骤会被跳过。

### 中文冰箱贴生成失败

检查中文字体和 `mapbox-earcut` 是否安装。脚本会根据 macOS、Windows、Linux 自动查找可用中文字体。

### 重新生成旧案例

默认会清理可再生的旧输出；需要保留旧文件时添加 `--keep-old-output`，或为不同案例指定不同的 `--output-root` 和 `--references-root`。

## 设计与数据约束

- GPX 和 EXIF 中的客观数据优先，不能凭空编造距离、日期、海拔或照片故事。
- 累计爬升按最高点减最低点计算：`max_elevation - min_elevation`。
- 生成前必须完成专家约束生成和校验。
- 交付物只记录专家包 ID、包内相对路径、trace ID、短 hash 和证据摘录，不写入本机绝对路径。

## 作者信息

- 作者：lumo
- 所属：同济大学设计创意学院
- 联系方式：1953430@tongji.edu.cn
