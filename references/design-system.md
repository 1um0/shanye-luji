# 设计系统参考 · 山野路迹

> 从设计大师 Skill 提取，经过户外徒步场景适配。在进行任何视觉生成前必须参考。

---

## 一、设计风格矩阵

每个品类对应一种主导设计风格与情感目标：

| 品类 | 主导风格 | 参考美学 | 情感目标 | 关键手法 |
|------|---------|---------|---------|---------|
| **3D 总结小报** | 纸雕等高线 + 机能风 | 诧寂 × 瑞士国际主义 | 纪念感、仪式感 | 纸质肌理、自然光、分层地形 |
| **冰箱贴** | 机能户外 + 极简几何 | 新自然主义 × 包豪斯 | 收藏欲、辨识度 | 异形裁切、单色山形、透明底 |
| **明信片** | 大字报拼贴 + 户外潮流 | Y2K × 诧寂 | 分享欲、情绪共鸣 | 大字标题、胶带拼贴、涂鸦箭头 |
| **公众号推送** | 东方极简 + 纪实摄影 | 诧寂 × 新自然主义 | 沉浸感、信任感 | 大留白、卡片式数据、故事叙事 |
| **九宫格组图** | 机能风 + 纪实混搭 | 赛博东方 × 包豪斯 | 冲击力、辨识度 | 黑底+荧光、网格系统、统一品牌栏 |

### 风格融合参考

| 融合 | 核心手法 | 本项目应用 |
|------|---------|-----------|
| 赛博 + 东方 | 霓虹色 + 传统纹样 + 科技字体 | 九宫格机能风配色 |
| 包豪斯 + 诧寂 | 几何形态 + 自然材质 + 不完美美学 | 冰箱贴异形裁切 |
| 极简 + 新自然 | 克制形式 + 有机曲线 + 单色调 | 明信片背面设计 |
| 机能 + 大地 | 数据可视化 + 暖色系 + 肌理材质 | 3D 小报纸雕风 |

---

## 二、统一配色系统

基于传统五行（木/土/火）映射到户外徒步语境：

| 令牌 | 色值 | 五行 | 心理效应 | 用途 |
|------|------|------|---------|------|
| `--pine` | `#6d8b5e` | 木（青） | 生机、自然、信任 | 山形剪影、标题辅助、植被色 |
| `--mineral` | `#5a7a6a` | 木（深绿） | 沉稳、专业、大地感 | 正文、数据标签、边框线 |
| `--earth-gold` | `#c4a87a` | 土（金） | 稳重、纪念、温暖 | 轨迹线、装饰线、强调色 |
| `--accent` | `#e07b3c` | 火（赤） | 活力、热情、警示 | 最高点标记、CTA 元素 |
| `--warm-sand` | `#e8dfd3` | 土（浅） | 安静、纸质、岁月 | 背景底色 |
| `--cream` | `#f5f0e8` | 金（白） | 纯净、高级、留白 | 明信片/冰箱贴基底 |
| `--dark` | `#1a1a1a` | 水（黑） | 深邃、高端、对比 | 正面背景、标题 |

### 配色禁忌
- 轨迹线不可用荧光绿（过于机能），用大地金（温和纪念感）
- 数据展示不可用纯黑（太硬），用矿物绿（柔和专业）
- 正面文字必须白色或大地金，不可用松针绿（与背景对比不足）
- 背面基底必须暖色（cream/沙色），不可用纯白（冷漠）

---

## 三、AI 绘图提示词模板

### 3.1 封面/海报主视觉

```
Chinese mountain landscape poster, [具体山峰] peaks,
layered contour lines paper-cut aesthetic, topographic map style,
warm earthy tones: sage green #6d8b5e, mineral #5a7a6a, gold #c4a87a,
organic curves, Japanese woodblock print influence,
clean composition, large negative space for text,
professional design, high quality
```

### 3.2 徒步纪念证/徽章

```
mountain adventure badge design, [路线名] traverse,
circular medal composition, mountain silhouette icon,
earth tones with gold accent, minimalist geometric,
hiking trail ribbon element, topographic background pattern,
vector style, clean lines, white background,
suitable for enamel pin or fridge magnet
```

### 3.3 户外实景 + 路线叠加

```
trail hiking route visualization overlay on landscape photo,
[描述：山脊线/林间/乱石坡], GPS track line glowing gold,
topographic contour background, outdoor adventure aesthetic,
moody natural lighting, golden hour atmosphere,
Chinese mountain range, misty peaks,
photography style, high contrast
```

### 3.4 冰箱贴包装/展示

```
fridge magnet set mockup, 4-piece outdoor hiking collection,
rectangle circle hexagon irregular mountain shapes,
wooden background, craft paper texture,
earth tone color palette, minimalist photography,
top-down flat lay, soft natural light,
product photography style --ar 1:1
```

### 3.5 国潮户外融合

```
Chinese traditional mountain landscape, modern outdoor aesthetic,
ink wash painting meets technical hiking gear,
山水画风格的现代徒步路线, contour lines as brush strokes,
vermilion seal stamp accents, rice paper texture,
Guochao outdoor style, elegant, premium quality
```

---

## 四、AI 生图流程

```
确定品类 → 选择模板 → 填入具体信息 → 生成 3-4 个变体 → 筛选最佳 → 裁剪适配
```

配合设计决策点：
1. **生图占 30%**：封面照片、装饰元素、纹理底图
2. **人工把控占 70%**：排版、信息层级、配色调整、品牌一致性

### 各品类生图需求

| 品类 | 生图内容 | 数量 | 输出格式 |
|------|---------|------|---------|
| 3D 小报 | 无需生图（Three.js 渲染，已有 SRTM） | — | — |
| 冰箱贴 | 山形轮廓参考、纹理底图（可选） | 0-2 | PNG 参考 |
| 明信片 | 正面背景照片（已有实拍）、装饰贴纸（可选） | 0-1 | JPG 嵌入 |
| 公众号推送 | 封面大图、段落插图 | 2-4 | JPG/PNG |
| 九宫格 | 各格底图（与实拍照片混排） | 0-3 | JPG 1080×1080 |

---

## 五、版式设计原则

### 5.1 网格系统
- 3D 小报：自由布局（Three.js 3D 场景 + 右侧固定面板）
- 冰箱贴：单对象居中，无需网格
- 明信片：正面无网格（大字报自由排版），背面两栏（400px + flex:1）
- 公众号：单栏流式（1080px 宽，上下滚动）
- 九宫格：3×3 严格网格（1080×1080 each）

### 5.2 亲密性原则
- 路线名 + 日期 → 紧邻形成标题区
- 里程/爬升/最高/耗时 → 4 个 pill 等距排列
- 照片 + 对应标注 → 距离 < 20px
- 轨迹线 + 标记点 → 标记点紧贴轨迹，标签偏移避开重叠

### 5.3 对比原则
- 正面：大字标题（88px/900 weight）vs 小字数据标签（9-11px）
- 背面：涂鸦区大面积留白 vs 顶部密集信息
- 色彩：大地金轨迹线在暗背景上形成最大对比

### 5.4 留白策略（诧寂风核心）
- 明信片背面涂鸦区 → 留白 > 60%，传达「你可以书写」
- 公众号导语区 → 上下留白 > 80px，营造呼吸感
- 冰箱贴 → 山形之外全部透明，形状本身就是留白

---

## 六、字体层级

| 层级 | 字号 | 字重 | 字体 | 用途 |
|------|------|------|------|------|
| H0 超级标题 | 88px | 900 | 跨平台中文黑体栈 | 明信片正面路线名 |
| H1 主标题 | 48-64px | 900 | 跨平台中文黑体栈 | 冰箱贴标题、小报标题 |
| H2 副标题 | 22-28px | 700 | 跨平台中文黑体栈 | 英文名、"四尖连穿" |
| H3 标签 | 16-20px | 600-800 | 跨平台中文黑体栈 | 品类标签、日期 |
| Body | 12-14px | 400 | 跨平台中文黑体栈 | 路线记录、故事正文 |
| Caption | 9-11px | 400-600 | 跨平台中文黑体栈 | 数据单位、页脚 |
| 英文 | — | 300-600 | Inter / 系统无衬线 | 英文副标题、装饰文字 |

跨平台中文黑体栈由 `scripts/platform_utils.py` 维护：Windows 优先微软雅黑，macOS 优先苹方/冬青黑体，Linux 优先 Noto/思源黑体。不要在新增脚本里硬编码单一系统字体。

### 字间距
- 中文标题（大字）：letter-spacing 8-18px
- 中文正文：letter-spacing 1-2px
- 英文全大写：letter-spacing 3-6px
- 装饰性英文：letter-spacing 2-4px

---

## 七、常见生图 prompt 反模式

| ❌ 避免 | ✅ 推荐 | 原因 |
|--------|--------|------|
| "beautiful mountains" | "Chinese mountain ridge, misty peaks" | 太抽象，产出随机 |
| "outdoor poster" | "hiking trail poster, paper-cut topographic" | 需要明确风格载体 |
| 只用英文 prompt | 中英双语提供文化语境 | 国潮/中式场景中文更精准 |
| 不指定色调 | "earth tones, sage green, mineral" | 不一致的配色会破坏品牌感 |
| 不指定比例 | "--ar 3:4" 或 "--ar 1:1" | 裁剪浪费 |
