# 角色 Mod 专项

## 一、注册三件套（modmain）

```lua
PrefabFiles = { "mychar" }
AddModCharacter("mychar", "FEMALE")     -- MALE/FEMALE/ROBOT/NEUTRAL/SECRET
modimport("scripts/data_avatar_mychar") -- 选人界面数据模块（可选）
-- modinfo 必须：character_mod = true + all_clients_require_mod = true
```

- 角色名对照（易错）：Maxwell=`waxwell`、Wigfrid=`wathgrithr`（prefabs/ 下无 maxwell.lua）。
- 文件夹名 = modname：测试副本改名后 mod RPC namespace 跟着变，客户端/服务端文件夹名必须一致。

## 二、prefab 骨架（MakePlayerCharacter 工厂）

```lua
return MakePlayerCharacter("mychar", prefabs, assets, common_postinit, master_postinit)
```

- 工厂自动：建实体、`SetBuild("mychar")`（**build 名必须 = prefab 名否则无贴图**）、
  注册全部玩家通用组件、挂 SGwilson。
- **common_postinit**（两端跑）：加 tag（自动同步）、两端组件、**netvar 声明**（见下）。
- **master_postinit**（仅服务端）：三维覆盖、专属组件、服务端事件、OnSave。
  附属自定义 prefab 才需要自己写 `if not TheWorld.ismastersim`（角色本体工厂已处理）。
- 三维基准（tuning.lua）：`WILSON 150/200/150`、`wilson_attack=34`、
  `WILSON_ATTACK_PERIOD=0.4`、`DEFAULT_ATTACK_RANGE=2`。
- 角色语音：`inst.soundsname = "willow"`（借用原版语音）。

## 三、自定义第四条数值（魔力/能量/怒气）六步法

照抄原版 health 组件的 **Class 第三参属性钩子**（赋值即回调同步），不要手写 Sync()。

1. **common_postinit 声明 netvar**（必须两端！放 master_postinit = 客机永远不动）：

```lua
inst.net_mana    = net_ushortint(inst.GUID, "mod_mana",     "mod_manadirty")
inst.net_manamax = net_ushortint(inst.GUID, "mod_mana_max", "mod_mana_maxdirty")
```

   dirty 事件名与变量名要对应（`变量.."dirty"`），别错位。
2. **master_postinit**：`inst:AddComponent("mana")`。
3. **scripts/components/mana.lua**：

```lua
local function oncur(self, v)
    if self.inst.net_mana ~= nil then self.inst.net_mana:set(math.floor(v)) end
end
local function onmax(self, v)
    if self.inst.net_manamax ~= nil then self.inst.net_manamax:set(math.floor(v)) end
end
local Mana = Class(function(self, inst)
    self.inst = inst
    self.max = 100
    self.current = 100          -- 构造时赋值即触发钩子同步初值（漏了 → 进游戏显示 0）
end, nil, { current = oncur, max = onmax })

function Mana:DoDelta(d) self.current = math.clamp(self.current + d, 0, self.max) end
function Mana:OnSave() return { current = self.current, max = self.max } end
function Mana:OnLoad(d)
    if d == nil then return end
    if d.max ~= nil then self.max = d.max end
    if d.current ~= nil then self.current = math.clamp(d.current, 0, self.max) end
end
return Mana
```

   （`scripts/components/` 下文件无需 modmain 引入，AddComponent 自动加载。）
4. **scripts/widgets/manabadge.lua**（继承原版 Badge 最省事）：

```lua
local Badge = require "widgets/badge"
local ManaBadge = Class(Badge, function(self, owner)
    Badge._ctor(self, nil, owner, {0.5, 0.6, 1, 1}, nil)
    self:UpdateMana()
    self.inst:ListenForEvent("mod_manadirty",     function() self:UpdateMana() end, owner)
    self.inst:ListenForEvent("mod_mana_maxdirty", function() self:UpdateMana() end, owner)
    self.inst:ListenForEvent("makeplayerghost",  function() self:Hide() end, owner)
    self.inst:ListenForEvent("respawnfromghost", function() self:Show() end, owner)
end)
function ManaBadge:UpdateMana()
    local net, netmax = self.owner.net_mana, self.owner.net_manamax
    if net ~= nil and netmax ~= nil and netmax:value() > 0 then
        self:SetPercent(net:value() / netmax:value(), netmax:value())  -- 第二参必须传真实上限！
    end
end
return ManaBadge
```

5. **modmain 挂 HUD**：

```lua
AddClassPostConstruct("widgets/statusdisplays", function(self)
    if self.owner == nil or not self.owner:HasTag("mychar") then return end
    local ManaBadge = require("widgets/manabadge")
    self.manabadge = self:AddChild(ManaBadge(self.owner))
    self.manabadge:SetPosition(self.column2, -100)   -- 饥饿条下方
end)
```

6. **回魔途径**——睡觉回魔复用原版 hook（不要自建 DoPeriodicTask：tent 没有 bedroll tag，
   自建判定必漏且醒来不取消任务）：

```lua
AddComponentPostInit("sleepingbaguser", function(self)
    local OldSleepTick = self.SleepTick
    self.SleepTick = function(cmp, ...)
        OldSleepTick(cmp, ...)
        local m = cmp.inst.components ~= nil and cmp.inst.components.mana or nil
        if m ~= nil and m.current < m.max then m:DoDelta(TUNING.MYMOD_SLEEP_MANA) end
    end
end)
```

排雷速查：显示空=初值没同步 / 客机不动=netvar 声明位置错 / 幽灵态没隐藏=没监听
makeplayerghost / 抄 GitHub 代码先查 `not a == b`（恒 false，应写 `a ~= b`）和未声明全局。

## 四、角色技能轮盘（spellbook + aoetargeting + aoespell，官方链路）

温蒂之花/麦斯威尔典书同款。三个组件挂同一"施法载体"实体（隐形 FX，SetParent 玩家）：

- `spellbook`（两端）：`SetItems(条目表)` 必须，否则轮盘秒关。条目
  `{label, onselect(inst)发RPC, bank/build="spell_icons_wendy", anims={idle/focus/down}, widget_scale=.6}`。
- `aoetargeting`（两端）：ctor 内 `net_bool "aoetargeting.enabled"`（SetPristine 前加）；
  `SetAlwaysValid(true)` + `SetAllowWater(true)` 让圈恒绿。
- `aoespell`（两端）：`SetSpellFn(fn(inst, doer, pos))` 返回 false = 施放失败。
- 打开：`ThePlayer.HUD:OpenSpellWheel(core, items, 175, 178)`（客户端专用服务器不注册按键）。
- **reticule 必须挂非玩家实体**（挂玩家身上落点永远在脚下）→ 学温蒂之花做法典实体。
- 轮盘 `onselect` 里 self.inst = **法典实体不是玩家**，要玩家用 `ThePlayer`。
- 施法距离：`aoetargeting:SetRange(n)` 一次设置永久生效（不是 ACTIONS.CASTAOE.distance）。
- 地图点选传送类：复用原版 `pocketwatch_portal_entrance`（SpawnExit/teleporter 全套现成）；
  `MapScreen:GetWorldPositionAtCursor()` 取光标坐标；落点校验服务端权威。

## 五、角色外观 build（ESCT 模板路线）

- **动作不用画**：全角色共用 wilson 骨架动画，角色 mod 只需 build（造型层）。
- 模板：`DragonWolfLeo/extendedsamplecharacter-dontstarvetogether`，156 帧零件库按符号分文件夹。
- **铁律：每帧画布尺寸 + pivot 绝对不动**，只换内容；build 名 = scml 文件名。
- 改名全局替换时 xml 内部 Element 名也要替换（avatar/bigportrait 等），否则图查不到。
- 重编译前**先删 anim/*.zip**（zip 只被改名时 scml.exe 假报 "up to date"）。
- ghost build 也要重编（模板带 ghost build 的 scml 源）。
- 美术细节（调色/AI 重绘/帧定位公式）较深，首次做角色建议直接在模板上换色起步。

## 六、官方人物模板路线（硬尺寸标准 + 18 项界面资产）

> 整理自 Klei 官方模板 `extended sample character-DST`（esctemplate，api_version 10），
> 汇编参考 zxiyx/dst-mod-creater 的逆向笔记；`AddModCharacter(name, gender, modes)`
> 三参签名已对照官方源码核实（modutil.lua:73）。

### 贴图尺寸硬标准（人物美术生成前必查，不得偏离）

| 用途 | 硬尺寸 |
|---|---|
| 角色动画贴图（Spriter 导入原图） | **1024x512 RGBA** |
| 存档槽头像 saveslot | **120x104** |
| 选人界面头像 selectscreen | **188x284**（另需 `_silho` 剪影版同尺寸） |
| 选人大肖像 bigportrait | **1024x1024**（源图 491x654 灰度胸像，编译前上色） |
| 小地图 map_icons / 头像 avatars×3（avatar/avatar_ghost/self_inspect） | 64x64 |
| 名称横幅 names / names_gold | png 源 876x434（编译后 tex 1024x512） |
| modicon | 128x128 |

- **选人界面 18 项资产**（modmain 逐项 Asset 声明，缺一项界面空白/报错）：
  saveslot / selectscreen(+silho) / bigportraits / map_icons / avatars×3 / names / names_gold
  / modicon 及各 .tex+.xml 产物；小地图另需 `AddMinimapAtlas("images/map_icons/xxx.xml")`。
- **names_[char].xml 陷阱**：编译后必须把 xml 里 **Element name 改成 `[角色名].tex`**
  （Texture filename 不动），否则选人界面角色名不显示。
- **幽灵 build 也要做**：`ghost_<build>.zip`（白色身体 + 雾 FX + 眼睛），
  配 `CreatePrefabSkin` 注册 `type="base"` 皮肤：
  `AddModCharacter("mychar", "FEMALE", { { type="ghost_skin", anim_bank="ghost", idle_anim="idle", scale=0.75, offset={0,-25} } })`。
- 语音表 `speech_<char>.lua`：整表抄 Wilson 基准（3000+ 行），只改自己要覆盖的条目；
  `STRINGS.CHARACTERS.MYCHAR = require "speech_mychar"`。
- 选人界面文案：`STRINGS.CHARACTER_TITLES/NAMES/DESCRIPTIONS/QUOTES/SURVIVABILITY`
  （DESCRIPTIONS 用 `\n` 逐行写天赋）。
- 部位帧数/pivot 标准：全角色共用 wilson 骨架，模板 20 部位 155 帧
  （face 33帧200x200 / torso 11帧160x120 / hand 20帧 / foot 8帧 …），
  **保持官方帧数与 pivot，只换像素**。
