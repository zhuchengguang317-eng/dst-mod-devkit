# 从零做一个能跑的 DST Mod（完整 Walkthrough）

本篇带一个从未写过饥荒 mod 的 AI 走完全流程：以「一把自定义武器」为例，
结构 / 代码 / 资产 / 测试全部给出可照抄的最小正确版本。其他类型 mod（食物/角色/植物）
换内容不换骨架。

## 0. 前置认知

- DST mod = 一个文件夹，最少两个文件：`modinfo.lua`（元信息）+ `modmain.lua`（入口）。
- mod 放在 `<DST安装目录>/mods/<你的mod名>/`。**文件夹名 = modname**，客户端/服务端必须一致。
- mod 分三类（写进 modinfo 的标志位，决定代码怎么写）：

| client_only_mod | all_clients_require_mod | 类型 | 适合 |
|---|---|---|---|
| true | false | 仅客户端 | 界面美化、汉化 |
| false | true | 全客户端 | **物品/角色/内容 mod（最常用）** |
| false | false | 仅服务端 | 纯服务器逻辑 |

- 游戏 Lua 脚本真值在 `<DST>/data/databundles/scripts.zip`，用 `scripts/dst_zip_tool.py` 查。

## 1. 项目结构

```
mymod/
├── modinfo.lua
├── modmain.lua
├── scripts/
│   └── prefabs/
│       └── mysword.lua        # 物品 prefab
├── anim/                      # 编译产物 zip（见 animation-assets.md）
├── images/
│   └── inventoryimages/
│       ├── mysword.xml        # 物品栏图标 atlas
│       └── mysword.tex
└── modicon.tex / modicon.xml  # 模组列表图标 128x128（可后补）
```

## 2. modinfo.lua（照抄改名字）

```lua
name = "My Sword",
description = "我的第一把武器",
author = "YourName",
version = "1.0.0",
api_version = 10,
dst_compatible = true,
all_clients_require_mod = true,   -- 内容 mod 必写
client_only_mod = false,
server_only_mod = false,

icon_atlas = "modicon.xml",
icon = "modicon.tex",
server_filter_tags = {"weapon"},

configuration_options = {
    {
        name = "damage",
        options = {
            { description = "42", data = 42 },
            { description = "68", data = 68 },
        },
        default = 42,
    },
},
```

- `description` 用 `\n` 转义换行，**禁止真实换行**。
- `configuration_options` 在 modmain 里用 `GetModConfigData("damage")` 读（只能 modmain 读）。

## 3. modmain.lua（逐行解释）

```lua
-- ① env 元表代理：modmain 第一件事，裸写引擎全局（TECH/STRINGS等）不再崩
do
    local setmetatable = GLOBAL.setmetatable
    local rawget = GLOBAL.rawget
    setmetatable(env, { __index = function(t, k) return rawget(GLOBAL, k) end })
end

-- ② PrefabFiles：声明 scripts/prefabs/ 下要加载的文件（字符串=文件名，见铁律）
PrefabFiles = {
    "mysword",
}

-- ③ Assets：所有资源在 modmain 顶层声明
Assets = {
    Asset("ANIM", "anim/mysword.zip"),
    Asset("ANIM", "anim/swap_mysword.zip"),          -- 手持贴图（见 animation-assets.md）
    Asset("ATLAS", "images/inventoryimages/mysword.xml"),
    Asset("IMAGE", "images/inventoryimages/mysword.tex"),  -- ★ 必须 .tex，写 .png 会崩
}

-- ④ 配置读取：裸调用 + nil 兜底（禁 pcall！GetModConfigData 用 pcall 包会直接崩）
local function Cfg(key, default)
    local v = GetModConfigData(key)
    if v ~= nil then return v end
    return default
end
GLOBAL.TUNING.MYSWORD_DAMAGE = Cfg("damage", 42)

-- ⑤ 名字与描述（STRINGS.NAMES 可裸写；DESCRIBE 要判表存在）
STRINGS.NAMES.MYSWORD = "圣剑"
STRINGS.RECIPE_DESC.MYSWORD = "一把锋利的剑"

-- ⑥ 配方：AddRecipe2（现代 API）
local mysword_recipe = { atlas = "images/inventoryimages/mysword.xml", image = "mysword.tex" }
AddRecipe2("mysword",
    { Ingredient("twigs", 2), Ingredient("flint", 3), Ingredient("goldnugget", 1) },
    TECH.SCIENCE_ONE,
    mysword_recipe,
    { "WEAPONS" })   -- 出现在哪个制作栏分类
```

- 常用 TECH：`TECH.NONE`（免科技）/ `TECH.SCIENCE_ONE` / `TECH.SCIENCE_TWO` / `TECH.MAGIC_TWO`。
- 常用制作栏 filter：`"WEAPONS" "TOOLS" "DRESS" "STRUCTURES" "REFINE" "MAGIC"`（大小写敏感，可用
  `dst_zip_tool.py grep "CRAFTING_FILTERS" --path-glob "scripts/recipes*.lua"` 查全表）。

## 4. scripts/prefabs/mysword.lua（逐行解释）

```lua
local assets = {
    Asset("ANIM", "anim/mysword.zip"),
    Asset("ANIM", "anim/swap_mysword.zip"),
}

local function onequip(inst, owner)
    owner.AnimState:OverrideSymbol("swap_object", "swap_mysword", "swap_mysword")
    owner.AnimState:Show("ARM_carry")
    owner.AnimState:Hide("ARM_normal")
end

local function onunequip(inst, owner)
    owner.AnimState:ClearOverrideSymbol("swap_object")
    owner.AnimState:Hide("ARM_carry")
    owner.AnimState:Show("ARM_normal")
end

local function fn()
    local inst = CreateEntity()

    inst.entity:AddTransform()
    inst.entity:AddAnimState()
    inst.entity:AddNetwork()

    -- ① 显示层到此为止（上面：Transform/AnimState/Network + 标签）
    inst.AnimState:SetBank("mysword")        -- bank = build.bin 里的 buildname
    inst.AnimState:SetBuild("mysword")
    inst.AnimState:PlayAnimation("idle")

    inst:AddTag("sharp")

    -- ② SetPristine 分界线：客户端到此返回（顺序永不变！）
    inst.entity:SetPristine()
    if not TheWorld.ismastersim then
        return inst
    end

    -- ③ 功能层：所有 AddComponent 只能写在守卫之后（仅服务端）
    inst.entity:AddSoundEmitter()            -- 有音效的实体必加，缺了播放就崩

    MakeInventoryPhysics(inst)
    MakeInventoryFloatable(inst, "med", 0.05, {1.1, 0.5, 1.1}, true, -9)

    inst:AddComponent("inventoryitem")
    inst.components.inventoryitem.imagename = "mysword"   -- ★ 不带 .tex！

    inst:AddComponent("equippable")
    inst.components.equippable.equipslot = EQUIPSLOTS.HANDS
    inst.components.equippable:SetOnEquipFn(onequip)
    inst.components.equippable:SetOnUnequipFn(onunequip)

    inst:AddComponent("weapon")
    inst.components.weapon:SetDamage(TUNING.MYSWORD_DAMAGE)

    inst:AddComponent("inspectable")
    inst:AddComponent("finiteuses")
    inst.components.finiteuses:SetMaxUses(150)
    inst.components.finiteuses:SetUses(150)

    MakeHauntableLaunch(inst)

    return inst
end

return Prefab("mysword", fn, assets)
```

**★★★ PrefabFiles 三一致铁律**：`PrefabFiles` 里的字符串 = 文件名 = `Prefab()` 第一个参数，
三者必须完全相同。不一致 = 服务器直接启动失败（`Error loading file prefabs/xxx`）。

**★★★ prefab 文件里禁止 `GLOBAL.` 前缀**（那是 modmain 的用法）；prefab 环境
直接裸用 `TUNING` / `TheWorld` / `EQUIPSLOTS`。

## 5. 资产（贴图/动画）最小可行路径

不画图先跑通逻辑：**借用原版资产**。
- `anim/mysword.zip`：暂时复制原版 spear 的 `anim/spear.zip` 改名为 `mysword.zip`（bank 名会不匹配 →
  先把 `SetBank/SetBuild("mysword")` 改为 `SetBank("spear")/SetBuild("spear")` 占位）。
- 图标：复制原版 `images/inventoryimages.xml` 里的 spear 条目逻辑太绕，最简单是先用
  `ktech.exe`（ktools）把一张 64x64 PNG 编成 `mysword.tex`：
  `ktech.exe mysword_64.png <mod>/images/inventoryimages/mysword.tex`，xml 用原版
  inventoryimages 任意 xml 复制改 Element name。
- 正式做贴图/动画/手持 swap：读 `references/animation-assets.md`。

## 6. 安装与静态校验

```bash
# 整目录拷贝（★ 用整目录 cp -r，单文件拷进不存在的目录会静默失败）
rm -rf "<DST>/mods/mymod" && cp -r ./mymod "<DST>/mods/mymod"

# 语法 + API 双检（都要跑）
python -c "from luaparser import ast; ast.parse(open('<mod>/scripts/prefabs/mysword.lua', encoding='utf-8').read())"
python scripts/check_api.py <mod>/scripts/prefabs/mysword.lua
```

（luaparser 需 `pip install luaparser`；没有就靠 dst_modtest 兜底，它同样能抓语法错。）

## 7. 无头测试（本技能核心交付保障）

```bash
python scripts/dst_modtest.py ./mymod --timeout 180
```

- PASS 标准：`LOADING LUA SUCCESS` + 世界创建成功 + 无 `LUA ERROR` / `Error loading mod!`。
- FAIL → 打开它给出的 `dst_modtest_last_run.log`，搜 `LUA ERROR` / `Error loading`，
  对照 `references/crash-playbook.md` 修 → 重测。
- 验证"能做出来/能装备"这类行为：写行为脚本（见 `references/testing.md`）。
- 详细用法、限制（画面观感/客户端渲染需真人进游戏验收）、残留进程清理见 `references/testing.md`。

## 8. 之后往哪走

| 想加什么 | 读 |
|---|---|
| 投掷 / 远程 / 弓箭 / 修复机制 | `items-and-weapons.md` |
| 锅料理、食物数值、17 角色检查台词 | `food-and-cooking.md` |
| 新角色（选人界面 + 专属数值/技能） | `characters.md` |
| 树/植物/世界生成 | `world-and-plants.md` |
| 联机同步、客户端 HUD | `networking.md` |
