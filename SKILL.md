---
name: dst-mod-devkit
description: |
  Don't Starve Together (DST / 饥荒联机版) mod development toolkit for AI agents.
  Teaches an agent that has NEVER written a DST mod how to build one end-to-end:
  project structure, modmain/prefab rules, Lua sandbox pitfalls, items/weapons/
  food/characters/plants, textures & animation compilation, crash triage, and
  HEADLESS TESTING (boot the game's own dedicated server to auto-verify the mod
  without launching the game).
  USE FOR: creating DST mods, adding items/weapons/food/characters, fixing mod
  crashes (no texture in hand / boot crash / MISSING strings), verifying or
  reviewing mods, headless mod testing.
  关键词: 饥荒 mod, 饥荒联机版模组, DST mod, modinfo.lua, modmain.lua, prefab,
  component, stategraph, TUNING, AddRecipe2, AddCookerRecipe, 手持无贴图,
  无头测试, dedicated server test.
  DO NOT USE FOR: other games' modding, DST server administration panels.
---

# DST Mod DevKit — 让 AI 从零做出能跑的饥荒联机版 Mod

本技能沉淀自 10+ 个已发布 DST mod 的完整开发流程（武器 / 食物包 / 角色 / 植物 / 特效），
全部规则都有官方源码行号或崩溃日志佐证。目标：**没写过饥荒 mod 的 AI 加载本技能后，
能独立完成一个 mod，并用无头测试自证它能跑。**

## 四条铁律（违反必出问题，按优先级排列）

### 1. 原版即真理，禁止凭记忆猜 API

- 任何 API / 常量 / 组件方法，先查官方源码再写。游戏脚本在
  `<DST安装目录>/data/databundles/scripts.zip`，用本技能的 `dst_zip_tool.py` 直接查（无需解包）：

  ```bash
  python scripts/dst_zip_tool.py grep "function.*:SetProjectile" --path-glob "scripts/components/*.lua"
  python scripts/dst_zip_tool.py show scripts/components/weapon.lua
  ```

- **学机制要找 ≥2 个同类原版实现对照**，多个实现共有的写法才是标准做法；只出现一次的写法要小心。
- 回答机制/数值问题优先查官方 wiki（dontstarve.wiki.gg），给结论带源码位置（如 `weapon.lua:97`）。

### 2. 验证 ≠ 语法检查，API 存在性必须跑脚本

`ast` 语法通过不代表方法存在（`inventory:Count()`、`SetOnPickUpFn` 这类写错的 API 语法完全合法但运行即崩）：

```bash
python scripts/check_api.py <你的prefab或组件.lua>   # 对照官方源码逐个验证组件方法
```

### 3. 交付前必跑无头测试（不进游戏自证 mod 能加载）

```bash
python scripts/dst_modtest.py <mod目录>              # 30~60 秒，PASS/FAIL + 退出码
python scripts/dst_modtest.py <mod目录> --script test.lua   # 附加行为测试
```

它会用游戏自带的专用服务器（`bin/dontstarve_dedicated_server_nullrenderer.exe`）离线启动
一次并加载你的 mod，能抓住约 90% 的"一开游戏就崩"。**未 PASS 不许宣称完成。**

### 4. 90% 的崩溃是少数几个坑

写代码前先读 `references/crash-playbook.md` 的对照表；出了问题先查
`documents/Klei/DoNotStarveTogether/` 下的日志（`master_server_log.txt` 信息最具体），
**先看日志再猜原因**。

## 标准工作流（每个 mod 任务都走一遍）

1. **分类任务**：新 mod / 加内容 / 修崩溃 / 审查他人 mod → 按下表路由到对应 reference。
2. **定位环境**：`dst_zip_tool.py` / `dst_modtest.py` 会自动探测 DST 安装目录
   （Windows 常见 Steam 路径扫 C-H 盘）；探测失败时问用户要路径，不要乱扫磁盘。
3. **查原版**：用 `dst_zip_tool.py` 找 2+ 个同类官方实现（如做树看 evergreens + palmconetree），
   确认 API 存在性与标准写法。
4. **搭骨架**：项目结构、modinfo、modmain 见 `references/first-mod.md`（第一次做照抄 walkthrough）。
5. **实现**：按路由表读对应 reference，写 modmain / prefab / 资产。
6. **静态校验**：Lua 语法检查 + `check_api.py` + `references/crash-playbook.md` 逐条排雷。
7. **无头测试**：`dst_modtest.py` 流程 A（启动测试）必跑；关键行为写流程 B 行为脚本。
   FAIL → 读日志 → 查 crash-playbook → 修复 → 重测，直到 PASS。
8. **交付**：跑 `references/release-checklist.md` 自检清单，向用户报告：改了什么、
   测试结果（PASS/FAIL + 日志关键行）、已知边界（无头测试测不了画面/音效观感，需用户进游戏验收）。

## 任务路由表

| 任务 | 必读 reference |
|---|---|
| 第一次做 mod / 新 mod 骨架 | `first-mod.md`（完整 walkthrough，从零到测试通过） |
| modmain / modinfo / 配置项 / 作用域 | `lua-and-prefabs.md` |
| 物品 / 武器 / 护甲 / 投掷 / 弓 / 配方科技 | `items-and-weapons.md` |
| 锅料理 / 食物 / 角色台词 | `food-and-cooking.md` |
| 角色 mod / 自定义三维 / 技能轮盘 / HUD | `characters.md` |
| 植物 / 树木 / 种植 / 世界生成 | `world-and-plants.md` |
| 联机同步 / RPC / replica / hook 原版 | `networking.md` |
| 贴图 / 动画编译 / 手持 swap / 特效 / 音效 | `animation-assets.md` |
| 崩了 / 不显示 / 报错 | `crash-playbook.md`（症状→根因→修法对照表） |
| 自测 / 行为测试 / 清理残留进程 | `testing.md` |
| 发布前最后检查 | `release-checklist.md` |

## 工具速查

| 工具 | 用途 | 示例 |
|---|---|---|
| `scripts/dst_zip_tool.py` | 在官方 scripts.zip 里直接 list/grep/show/extract（带缓存，零依赖） | `python scripts/dst_zip_tool.py grep "STACK_SIZE_CODES" --path-glob "scripts/*.lua"` |
| `scripts/check_api.py` | 校验 Lua 里组件方法/实体方法是否存在（防 nil 崩溃） | `python scripts/check_api.py myweapon.lua` |
| `scripts/dst_modtest.py` | 无头启动 + 行为测试，PASS/FAIL + 退出码（CI 友好） | `python scripts/dst_modtest.py ./MyMod --timeout 180` |

三个工具都纯 Python 标准库、零第三方依赖、跨平台（Windows/Linux/macOS 自动探测路径，
找不到就用 `--dst "<安装目录>"` 显式指定）。

## 高频坑速览（详情见 crash-playbook.md）

- `modmain` 第一行必须写 env 元表代理，否则 `GLOBAL.X` 死局；`scripts/` 下的 prefab/组件
  **禁止**用 `GLOBAL.` 前缀（反过来）。
- **`FOODTYPE.FISH` 不存在**（鱼用 `FOODTYPE.MEAT`）；写了 = 食物变不可食用。
- 物品栏贴图：`Asset("IMAGE", ...)` 必须 `.tex` 不是 `.png`；`imagename` 不带 `.tex`；
  alpha≥250 白底会把食物渲染成白方块。
- swap 手持动画名只能 `BUILD_90s_90s` 或 `BUILD`，写 `idle` = 手持无贴图。
- `modmain` 顶层禁止用 `TheWorld`（世界还没创建，服务器直接起不来）。
- 动画 zip 必须 `build.bin + anim.bin + atlas-*.tex` 三件齐全；动画控制在 60 帧量级
  （149 帧实测客户端无法启动）。
- netvar 的 `value()` 是只读 getter，设置必须 `:set()`；`set()` 值没变不触发 dirty 事件。
- 跑完无头测试必须清残留进程（占 10999 端口会让用户自己的服务器起不来）。

## 绝对禁止

- ❌ 禁止用本地 `lua`/`luac` 验证 mod 代码（DST 是 Klei 魔改 Lua 运行时，结果无意义）。
- ❌ 禁止覆写引擎全局：`GLOBAL` / `TheSim` / `TheNet` / `TheWorld` / `ThePlayer` / `TUNING` 整表替换。
- ❌ 禁止整段复制大型官方文件进 mod（用窄 hook：post-init / AddComponentPostInit）。
- ❌ 禁止在 `scripts/`（prefab/组件/widget）里用 `GLOBAL.` 前缀或 modmain 的自定义 env 变量。
- ❌ 禁止修改用户的动画资产（.scml）而不先告知；纯重建编译优先，改动需用户同意。
- ❌ 禁止没跑 `dst_modtest.py` 就声称 mod 完成。
