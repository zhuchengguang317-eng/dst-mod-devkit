# 贴图 / 动画编译 / 手持 swap / 特效 / 音效

## 一、贴图预处理（食物/物品通用）

- **抠图三步法**（缺一步 = 游戏里白方块）：① rembg 或白底阈值抠图 → ② 内容 bbox 对齐 →
  ③ **bbox 外圈 alpha=0**。禁止 alpha=255 白底直接编 tex（渲染成白方块）。
- 尺寸规格：物品栏 64×64 / 地面 256×256 / 动画格约 200×132（锅内食物）。
- DST 画风提示词要点（AI 生图）：`Don't Starve game art style, Tim Burton whimsical gothic,
  rough sketchy wobbly dark brown ink outlines, flat muted desaturated colors, no shading,
  no cast shadow, plain pure white background, game inventory icon style`；
  负面元素写进描述而非 "no xxx"（模型容易反向强调）。
- 后处理：压暗去饱和（亮度×0.82、饱和度向灰 25%）去高光，贴近原版灰调。

## 二、动画编译管线

工具链三选一（推荐 A）：

**A. 官方 scml.exe（Windows Mod Tools，最稳）**

```bash
cd "<Steam>/common/Don't Starve Mod Tools/mod_tools"
./scml.exe "<mod>/exported/xxx.scml" _scmlout     # 产物 _scmlout/anim/xxx.zip
```

- **绕开 autocompiler**：它内部 resize.py 会静默重编码 PNG + 假报 "up to date"
  （zip mtime 变新但内容没编 → **先删 anim/*.zip 再编译**）。
- SCML 规则：**folder name = 符号名**（build.bin symbol = folder 名）；entity name = build 名
  （SetBank/SetBuild 用）；PNG 路径 = `folder名/xxx-0.png`（必须子目录）；pivot 每图独立。

**B. buildanimation.py（Mod Tools 自带，Python27）**——帧序列直接编 anim zip
（特效/法阵等无 Spriter 素材），详见第四节特效。

**C. ktools（ktech + krane）**

- `ktech.exe <file.tex> <输出目录>` 解码 PNG；`ktech.exe <png> <out>/xxx.tex` 编码
  （★ 位置参数，没有 -o 选项；不认中文路径 → 先拷 ASCII 路径）。
- `krane.exe <解压目录> <输出>` 把 anim zip 反编译回 SCML（拆原版资源学习用）。
- 物品栏图集 xml 手写：Element name **不带 .tex**；UV 坐标 u1/u2/v1/v2。

### anim zip 三件套铁律

zip 内必须 `build.bin + anim.bin + atlas-*.tex` **三件齐全**——脚本按扩展名收集极易漏 .tex，
产物全空白且无报错。打包后必须 `zipfile.namelist()` 打印核对：

```python
import zipfile, re
z = zipfile.ZipFile("mysword.zip")
print(z.namelist())                       # 期望: build.bin, anim.bin, atlas-0.tex
print(re.findall(rb"[ -~]{4,}", z.read("build.bin")))   # BILD + build名x2 + atlas名
print(re.findall(rb"[ -~]{4,}", z.read("anim.bin")))    # 动画名
```

- **SetBank 的参数 = build.bin 里的 buildname**（不是 zip 文件名！）——两者不一致时
  SetBank 报 `Could not find anim bank`。排查无贴图先解 build.bin 对比。

### 帧数铁律

- 动画控制在 **60 帧量级**：实测 149 帧（哪怕单 2048² 图集）客户端直接无法启动。
- 长动画**降 fps 不加帧**（60帧@6fps = 10 秒）；需要更流畅 = 均匀重采样保时长。
- 单 symbol 的帧**绝不跨图集**（原版从不这么排，--square 也救不了）→ 装不下就缩帧 +
  `AnimState:SetScale(x,x,1)` 补大小。
- 改 PNG 必须重编对应 anim zip；改 Lua 不用重编美术。

## 三、手持 swap build（"手持无贴图"专项）

1. swap SCML 动画名：`BUILD_90s_90s` 或 `BUILD`（都验证有效），**唯一禁用是 `idle`**
   （找不到动画 = 手持无贴图，踩过 3+ 次）。
2. 三要素一致：**folder 名 = build 名 = OverrideSymbol 第三参 = `swap_xxx`**；
   timeline name = build 名；bank名=symbol 名（build.bin 里 build 名应出现 2 次）。
3. Lua 一行就够（无需 AddOverrideBuild）：

```lua
owner.AnimState:OverrideSymbol("swap_object", "swap_mysword", "swap_mysword")
```

4. **紧凑画布**：长宽比 ≥6:1 的细长武器必须 100% 宽填满画布（水平不留透明边距），
   否则缩成"牙签"看着像没贴图。推荐 200×H，pivot_y = 柄部位置（0.72~0.93）。
5. 帽子 `OverrideSymbol("swap_hat", build, "swap_hat")` + Show("HAT")/Show("HAT_HAIR") +
   Hide("HAIR_NOHAT") + Hide("HEAD")/Show("HEAD_HAT")（全遮帽；不遮头发的花环变体只 Show HAT）。
6. 护甲同款 `swap_body`。装备 on equip 回调重复定义只生效最后一个（二选一）。

## 四、特效（GIF/webp/静态图 → anim zip）

- 帧序列打 stage zip（build.xml + animation.xml + frame_NN.png）→ buildanimation.py 编译：

```bash
cd "<Mod Tools>/mod_tools/tools/scripts"
"<Mod Tools>/mod_tools/buildtools/windows/Python27/python.exe" buildanimation.py \
  "<stage>.zip" --force --ignoreexceptions --outputdir "<输出目录>"
# 产物 <输出目录>/anim/<stage名>.zip
```

- **Frame x/y（build.xml）= 帧中心相对原点偏移**；**frame x/y（animation.xml）= 内容左上角
  = 中心偏移 -w/2、-h/2**——两处语义不同，写错引擎当裁剪框切出直边碎片。
- 原点锚"视觉落点"（落点圈=圈中心对原点），别用整体质心（柱状主体会污染偏移）。
- framerate 必须整数；多图集加 `--square`（但首选单图集）。
- 游戏内：

```lua
inst.AnimState:SetBank("sacred_thunder")
inst.AnimState:SetBuild("sacred_thunder")
inst.AnimState:PlayAnimation("idle")
inst.AnimState:SetScale(8, 8, 1)    -- ★ 必须 SetPristine 之前（本地渲染属性不联网）
-- 播完 ListenForEvent("animover") Remove
```

- 尺寸心算：1 格 ≈ 200 动画单位；发光 `SetBloomEffectHandle("shaders/anim.ksh")`。

## 五、自定义音效（FMOD fev/fsb）

- mod 音频必须走 FMOD：`Asset("SOUNDPACKAGE","sound/x.fev")` + `Asset("SOUND","sound/x.fsb")`。
- 工具就在 Mod Tools：`fmod_designercl.exe -pc -b <outdir> <project.fdp>`（.fdp 是 XML，
  从带声音的 mod 抄模板改 GUID/wav 路径；音频先 `ffmpeg -c:a pcm_s16le` 转 PCM wav，
  44.1kHz/16bit）。
- 事件路径 = 项目名/组名/事件名（组名用小写 `sound`），PlaySound 用完整字符串；
  **FSB5 格式本身不崩**（原版全是 FSB5）——客户端崩先查 wav 参数而非容器格式。
- 构建后查 fsb 大小 ≈ wav 字节数（192 字节 = 静默空壳，SUCCESS 日志不可信）。
- 3D 空间感：fdp 里 `x_2d` → `x_3d` + mindistance/maxdistance 调整。
- 排查：DST 原版音效就是 FSB5，"格式必崩"是误诊；抓 client_log / minidump 看真凶。

## 六、贴图/图集 API 细节

- `Asset("IMAGE", ...)` 必须 `.tex`（PNG → "not a valid Klei texture" 连锁崩）。
- 图集 xml（物品栏）：`<Atlas><Texture filename="images/.../xxx.tex"/><Elements>
  <Element name="xxx" width="64" height="64" u1..v2/></Elements></Atlas>`。
- 食谱书/图鉴不显示贴图：`RegisterInventoryItemAtlas("images/xxx.xml", "xxx")`（第二参不带 .tex）。
- 64×64 DXT 压缩后文件大小可能相同 → 判"是不是同一张图"用 md5 不用字节数。
