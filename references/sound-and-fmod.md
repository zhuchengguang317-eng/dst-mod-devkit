# 音效制作（FMOD fev/fsb 全流程）

DST 音频**必须走 FMOD 事件银行**：m4a/mp3/ogg/裸 wav 不能直接播。
本篇是端到端管线（实战验证于魔法阵音效与朗基努斯命中音），不装 FMOD GUI 全程 CLI 完成。
工具入口：`<Steam>/common/Don't Starve Mod Tools/mod_tools/FMOD_Designer/fmod_designercl.exe`（FMOD 4.44.07 CLI）。

## 流程总览

```
素材 mp3/ogg/任意音频
 → ① ffmpeg 加工成规范 wav（裁剪/回声/混音/响度）
 → ② 写 .fdp 工程文件（模板法，.fdp 本质是 XML）
 → ③ fmod_designercl 编译 → <project>.fev + <project>.fsb
 → ④ QC（fsb 大小 + strings 校验）
 → ⑤ 代码端接入（Asset 声明 + PlaySound）
 → ⑥ 无头实测 + 真人进游戏验收
```

## ① wav 加工（ffmpeg）

- **格式铁律**：44.1kHz / 16bit / stereo PCM：

```bash
ffmpeg -i in.mp3 -ar 44100 -ac 2 -c:a pcm_s16le out.wav
```

- ★ Windows 版 ffmpeg 不认 Git Bash 的 `/d/` 风格路径，**必须传 `D:/` 风格**。
- 裁剪：`-ss 0 -t 1.3`；**切点必须 de-click**（末端 `afade=t=out:st=<dur-0.03>:d=0.03`，否则咔哒声）。
- 回声：`aecho=in:out:0.45|0.9|1.35:0.6|0.4|0.27`（delays|decays，N 段一次写完）。
- 双层混音：`amix=inputs=2:duration=longest:normalize=0`（★ `normalize=0` 必加，否则整体被压小）。
- 起始偏移：`adelay=150|150`（ms，双声道各一份）；限幅：`volume=X:precision=float` 后接 `alimiter` 防爆音。
- **★ 音量铁律（实测教训）**：加工链顶到 peak 0dBFS 的成品，游戏里"声音特别大"
  （游戏内还会叠加场景增益）。**成品 wav peak 控制在 -10dB 左右**：
  `ffmpeg -i in.wav -af volume=-10dB out.wav`，然后重编译 bank。
- 素材来源响度差异大（如视频片段）可先 `loudnorm`，但最终仍要查 peak。

## ② .fdp 模板法（不装 FMOD GUI）

找 workshop 里带声音的 mod 抄 `.fdp` 模板（XML），必改五处：

1. 项目/银行/事件组/事件名（项目名 ≠ 银行名时，以**事件路径拼接**为准）。
2. **全部 GUID 用 uuid4 重新生成**（正则替换 `{...}`，漏改会撞 GUID）。
3. `<waveform><filename>` 指向自己的 wav。
4. **事件组名用小写 `sound`**（社区约定，如 `mymod/sound/hit`）。
5. 一次性音效：模板的 `loopmode=1, loopcount2=-1` 表现就是播一次，不用动。

**空间感（3D 衰减）**：`<mode>x_2d</mode>` → `x_3d`，`mindistance 1→3`、
`maxdistance 10000→30`——**fdp 里有两处**（event 属性 + waveform 默认值），
**漏一处就不衰减**；x_2d = 全图满音量。

## ③ 编译

```bash
mkdir -p <outdir>    # ★ outdir 必须先建，否则报 Can't find
fmod_designercl.exe -pc -b <outdir> <project.fdp>
# 产物：<project>.fev + <project>.fsb
```

## ④ QC（构建后必做）

- **fsb 大小 ≈ wav 原始 PCM 字节数 = 正常；192 字节 = 静默空壳**。
  编译日志 SUCCESS 不可信，**只看大小**。
- `strings xxx.fev` 应能看到 项目名/组名/事件名；改过 fdp 重编译后先校验再接入。
- **"FSB5 必崩"是误诊**：DST 原版 data/sound/ 与可用 mod bank 全是 FSB5 ver1。
  客户端真崩先查 wav 参数（44.1k/16bit/stereo）而非容器格式。

## ⑤ 代码端接入

```lua
-- modmain 或 prefab 的 Assets（两处声明都要 .fev + .fsb 成对）
Asset("SOUNDPACKAGE", "sound/mymod_hit.fev"),
Asset("SOUND", "sound/mymod_hit.fsb"),
-- 播放：事件路径 = 项目名/sound/事件名（.fdp 里拼出来的全名，直接抄）
ent.SoundEmitter:PlaySound("mymod/sound/hit")
```

- **PlaySound 必须挂在有位置的实体上**（`ent.SoundEmitter`）；挂 TheWorld/全局 = 等于 2D。
- 有音效的实体 prefab **必须 `inst.entity:AddSoundEmitter()`**（缺了播放即崩）。
- **替换原版音效**（官方模板 samplesound 同款）：

```lua
RemapSoundEvent("dontstarve/creatures/bat/flap", "mymod/sound/bat_flap")
-- 第一参游戏原事件全名；第二参 mod 内事件全名（不带 bank 名的 fdp 层级路径）
```

- 3D 空间感参数在 fdp 层调（mindistance/maxdistance）；播放层变调/音量用
  `PlaySound(event, name, ...)` 的变体或 FMOD 层做，**源 wav 保持干净母带**。

## ⑥ 无头实测（不进游戏验证 bank 能加载）

用 `dst_modtest.py --script`（见 testing.md 流程 B）：

```lua
-- test_sound.lua
local ent = SpawnPrefab("spear")        -- 任意带 SoundEmitter 的实体
ent.SoundEmitter:PlaySound("mymod/sound/hit")
print("[MODTEST] SOUND PLAYED OK")
GLOBAL.c_shutdown()                     -- os.exit 在 DST 沙箱里是 nil！
```

`[MODTEST] SOUND PLAYED OK` 出现 = bank 加载 + 事件查找通过。
**局限**：专用服务器 FMOD 是 nosound——混音崩溃、实际音量、空间感只能真人进游戏验收
（交付时必须向用户声明）。

## ⑦ 交付包结构（给代码端/协作者）

```
DST音效素材/
├── sound/          # mymod_hit.fev + .fsb（每事件一对）
├── wav/            # 对应 wav 源（复用/再加工备用）
└── 接入说明.txt    # 事件完整路径 / Asset 写法 / 3D 参数 / 设计参数
                    # （时长/层数/回声规格/peak dB）/ QC 记录 / 音量修正版本史
```

## 排查对照表（实测反馈两连报的结论）

| 症状 | 根因 | 修法 |
|---|---|---|
| 声音特别大 | wav peak 顶 0dBFS + 游戏内场景增益叠加 | wav 压到 -10dB 重编译 bank（别让代码端 compensate）；改完核对 fsb 大小 |
| 没有空间感/不衰减 | ① PlaySound 挂在 TheWorld/全局；② fdp 两处 x_2d 只改了一处 | 挂到有位置实体；event + waveform 两处都改 x_3d；注意 mindistance=3 时 3 格内满音量是正常，别误判 |
| 编译报 Can't find | outdir 目录不存在 | 先 mkdir |
| fsb 是 192 字节 | wav 未被真正打进（路径/格式错） | 查 fdp 里 waveform filename 与 wav 参数；SUCCESS 日志不可信 |
| 客户端进游戏崩 | 多半是 wav 参数（采样率/位深）而非 FSB5 | 对齐 44.1k/16bit/stereo PCM |
| fsb 没跟上 wav 修改 | fsb 不会自动重编 | 改 wav 必须重编译 bank |

---
> 依赖知识：Asset 声明见 first-mod.md；无头测试见 testing.md；
> 官方 samplesound 模板（fev/fsb/fdp 结构与 RemapSoundEvent）解析参考 zxiyx/dst-mod-creater。
