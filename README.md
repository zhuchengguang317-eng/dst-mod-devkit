# dst-mod-devkit

**让 AI 从零做出能跑的《饥荒联机版》(Don't Starve Together) Mod 的 Agent Skill 工具包。**

[English](#english) | 中文

---

## 这是什么

一个面向 AI 编程助手（Claude Code / Codex / WorkBuddy 等支持 Agent Skills 的工具）的
技能包：AI 加载本技能后，即使它**从未写过饥荒 mod**，也能独立完成
「写代码 → 做资产 → 自测 → 交付」全流程。

- **11 篇分层参考文档**：从第一个 mod 的完整 walkthrough，到物品/武器/料理/角色/植物/
  联机同步/动画编译/音效制作，按需加载（渐进式披露，不浪费上下文）。
- **40+ 条崩溃对照表**：症状 → 根因 → 修法，全部来自真实崩溃日志与官方源码行号佐证。
- **3 个零依赖工具**（纯 Python 标准库，跨平台）：
  | 工具 | 功能 |
  |---|---|
  | `dst_zip_tool.py` | 直接 list/grep/show/extract 官方 `scripts.zip`，写代码前查 API 不用解包 |
  | `check_api.py` | 校验 mod 代码里调用的组件方法是否真实存在（防"语法对但运行必崩"） |
  | `dst_modtest.py` | **无头测试**：用游戏自带专用服务器离线启动 mod，30~60 秒输出 PASS/FAIL；行为脚本（`--script`）的 return 值会被类型化序列化回传，支持真值断言 |

## 为什么需要它

DST mod 开发的崩溃高度模式化：`GLOBAL.` 误用、Pristine 顺序错、API 大小写错
（`SetOnPickUpFn`）、`FOODTYPE.FISH` 不存在、swap 动画名写 `idle`……
这些坑 AI 靠猜必踩。本技能把它们固化成铁律 + 检查清单 + **自动化校验工具**，
并让 AI 在交付前用无头服务器自证 mod 能加载——不把"应该能跑"丢给用户。

## 安装

把整个 `dst-mod-devkit/` 文件夹放进你的 Agent 工具的技能目录：

| 工具 | 位置 |
|---|---|
| Claude Code | `~/.claude/skills/` |
| Codex CLI | `~/.agents/skills/` |
| WorkBuddy | `~/.workbuddy/skills/` |

要求：本机装有《饥荒联机版》（专用服务器二进制随本体附带），Python 3.8+。

## 快速上手（给 AI 的一句话）

> 按 SKILL.md 的标准工作流开发 DST mod：先读 first-mod.md，用 scripts/dst_zip_tool.py
> 查官方源码，写完跑 scripts/check_api.py，交付前必须 scripts/dst_modtest.py PASS。

## 目录结构

```
dst-mod-devkit/
├── SKILL.md                      # 入口：四条铁律 + 标准工作流 + 任务路由表
├── references/
│   ├── first-mod.md              # 从零到测试通过的完整 walkthrough（新手必读）
│   ├── lua-and-prefabs.md        # Lua 作用域/沙箱陷阱/Pristine/netvar/组件 API 查证表
│   ├── items-and-weapons.md      # 物品/武器/投掷/弓箭/配方/皮肤
│   ├── food-and-cooking.md       # 锅料理/食物数值/17 角色台词规则
│   ├── characters.md             # 角色 mod/自定义三维/技能轮盘/HUD
│   ├── world-and-plants.md       # 植物树木/种植/世界生成
│   ├── networking.md             # replica/RPC/hook/客户端 HUD
│   ├── animation-assets.md       # 贴图/SCML 编译/手持 swap/特效/KTEX 格式
│   ├── sound-and-fmod.md         # 音效全流程：wav 加工/fdp 模板/编译/QC/排查
│   ├── crash-playbook.md         # 崩溃对照表（症状→根因→修法，40+ 条）
│   ├── testing.md                # 无头测试完整指南
│   └── release-checklist.md      # 发布前自检清单
└── scripts/
    ├── dst_zip_tool.py           # scripts.zip 直查（带缓存）
    ├── check_api.py              # API 存在性校验
    └── dst_modtest.py            # 无头启动+行为测试（vendored from dst-modtest）
```

## 边界与说明

- 无头测试覆盖启动/加载/服务端行为；**画面观感、音效听感、纯客户端崩溃仍需真人进游戏验收**
  （工具文档中已要求 AI 主动向用户说明这一点）。
- 游戏更新后 `dst_zip_tool.py` 缓存自动失效重建。
- 欢迎补充崩溃案例与工具改进（PR 请附日志/源码行号佐证，与本技能的规则标准一致）。

## 致谢

- 无头测试工具来自 [dst-modtest](https://github.com/zhuchengguang317-eng/dst-modtest)。
- 技能结构设计参考了 [KyuubiRan/dst-mod-skill](https://github.com/KyuubiRan/dst-mod-skill) 的
  渐进式披露思路。
- 人物硬尺寸标准 / KTEX 纹理格式逆向 / TileManager.AddTile 地皮注册等章节，
  整理时参考了 [zxiyx/dst-mod-creater](https://github.com/zxiyx/dst-mod-creater) 的逆向笔记
  （相关 API 已逐一对照官方源码核实）。
- 经验沉淀自 10+ 个已发布 DST mod 的开发实践。

---

<a name="english"></a>
## English

An Agent Skill that teaches an AI coding assistant (Claude Code / Codex / etc.) to build
working Don't Starve Together mods end-to-end — even with zero prior DST modding knowledge.

**Contents**: 11 layered reference docs (progressive disclosure), a 40+ entry
symptom→cause→fix crash playbook backed by game-source line numbers, and 3 dependency-free
Python tools: `dst_zip_tool.py` (query the official scripts.zip directly), `check_api.py`
(verify component methods exist before runtime crashes), and `dst_modtest.py` (**headless
testing**: boot the game's own dedicated server offline, PASS/FAIL in ~60s).

**Install**: drop the folder into your agent's skills directory
(`~/.claude/skills/`, `~/.agents/skills/`, `~/.workbuddy/skills/`, ...).
Requires DST installed + Python 3.8+.

**Headless testing** verifies boot/loading/server-side behavior; visual result, audio, and
pure-client crashes still need human in-game verification (the skill instructs the agent to
say so explicitly).
