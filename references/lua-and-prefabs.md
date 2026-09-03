# Lua 环境与 Prefab 规则（写代码前必读）

DST 的 modmain 和 prefab 是**两套不同的执行环境**，90% 的"我明明写了"类 bug 源于混用。

## 一、两种作用域（最重要）

| 文件 | 环境 | 引擎全局写法 | modutil 函数 |
|---|---|---|---|
| `modmain.lua`（及 modimport 的文件） | mod 沙箱 env + strict | `GLOBAL.XXX` 或开头 env 代理后裸写 | **裸调用**（AddRecipe2 / AddPrefabPostInit...） |
| `scripts/prefabs/*.lua`、`scripts/components/*.lua`、`scripts/widgets/*.lua` | `=_G + strict 模式` | **直接裸用**（TUNING/TheWorld/SpawnPrefab） | ❌ 不存在！modutil 只在 modmain |

- prefab/组件里写 `GLOBAL.XXX` → `variable 'GLOBAL' is not declared` 直接崩。
- modmain 里写自定义全局变量（如 `Loc`）后，`scripts/` 下的文件**看不到它**（env 不跨文件），
  用了就崩 `variable 'Loc' is not declared`。跨文件传值只能走 `TUNING.*` / `STRINGS.*` / `_G.X`。
- **modmain 顶层禁止用 `TheWorld`**（世界还没创建）：
  `TheWorld:ListenForEvent(...)` 在顶层 → 服务器完全启动不了，mod 被禁用。
  世界级监听用 `AddPrefabPostInit("world", function(inst) inst:ListenForEvent(...) end)`。

### env 元表代理（独立 mod 的 modmain 第一行）

```lua
do
    local setmetatable = GLOBAL.setmetatable
    local rawget = GLOBAL.rawget
    setmetatable(env, { __index = function(t, k) return rawget(GLOBAL, k) end })
end
```

之后 `TECH` / `STRINGS` / `Ingredient` 等裸写即可。不写的话 `local TECH = GLOBAL.TECH` 这类
写法有一批符号会取到 nil（`AddRecipe2`/`GetLocale`/`SCIENCE` 单数名等根本不在 GLOBAL 上）。

### 沙箱禁用函数

`pcall` / `xpcall` / `dofile` / `loadstring` 被沙箱剥离，用了直接崩（**注释里残留也要清理**）。
配置读取用 nil 兜底模式：

```lua
local function Cfg(key, default)
    local v = GetModConfigData(key)
    if v ~= nil then return v end
    return default
end
```

`GetModConfigData` 只能在 modmain 用；prefab 里要读配置 → modmain 注入
`GLOBAL.TUNING.MYMOD_X = Cfg(...)`（modmain 先于 prefab 执行）。

## 二、Prefab 骨架铁律（Pristine 顺序）

```lua
local inst = CreateEntity()
inst.entity:AddTransform()      -- 显示层：Transform/AnimState/Network/Light + 标签
inst.entity:AddAnimState()
inst.entity:AddNetwork()

inst.AnimState:SetBank("xxx")   -- ★ bank = build.bin 里的 buildname（不是 zip 文件名！）
inst.AnimState:SetBuild("xxx")

inst.entity:SetPristine()       -- ① 分界线
if not TheWorld.ismastersim then return inst end   -- ② 客户端守卫（永不变）
inst.entity:AddSoundEmitter()   -- ③ 功能层：所有 AddComponent / 服务端逻辑
inst:AddComponent("inspectable")
```

- 客户端右键菜单需要的 inst 方法/字段必须挂 **SetPristine 之前**。
- **本地渲染属性不联网**：`AnimState:SetScale` / `SetBloomEffectHandle` / `SetOrientation` /
  `SetDeltaTimeMultiplier` 写在守卫之后只有服务端变，客户端画面纹丝不动（FX 特效"没放大"的头号原因）。
  必须写在 SetPristine **之前**的公共区（两端各自执行）。
- **组件存档签名是返回值式**：`function Comp:OnSave() return {hp=...} end`、
  `function Comp:OnLoad(data)`。写成往参数 data 里赋值 = 存不上（引擎只取返回值）。

## 三、netvar 网络变量（客户端拿服务端数据的基础）

```lua
-- 声明（必须两端都执行 → 放 common_postinit / SetPristine 之前，不能放 master_postinit）
inst.net_mana = net_ushortint(inst.GUID, "mod_mana", "mod_manadirty")

-- 服务端写：必须 :set()；value() 是只读 getter（传参被忽略，写了不报错但永远不生效！）
inst.net_mana:set(100)

-- 客户端读：net:value()；变化通知 = ListenForEvent("mod_manadirty", fn, owner)
```

- 10 种类型：`net_bool / net_string / net_entity / net_ushortint / net_byte / net_tinybyte /
  net_smallbyte / net_float / net_event / net_smallbytearray`。
- **值没变化不触发 dirty 事件** → HUD 类 UI 必须加轮询兜底（`StartUpdating(1)`）或初始主动刷一次。
- RPC / netvar 全是异步：发完立刻读 replica 取不到新值。

## 四、组件 API 查证表（凭记忆写 = 崩，先跑 check_api.py）

| 组件/对象 | ✅ 有效 | ❌ 不存在（实崩案例） |
|---|---|---|
| inventory | `ForEachItem` `FindItems(fn)` `ConsumeByName` `GetEquippedItem` `DropItem` `NumItems` | **`Count()`** |
| inventoryitem | `SetOnDroppedFn` **`SetOnPickupFn`** `SetOnPutInInventoryFn` | **`SetOnPickUpFn`**（Pickup 不是 PickUp） |
| stackable | `maxsize` 是**属性**：`inst.components.stackable.maxsize = TUNING.STACK_SIZE_MEDITEM` | **`:SetMaxSize()` 调用**（nil 崩）；maxsize 只接受 STACK_SIZE_CODES 预定义值（写 999 → nil 算术崩） |
| hunger（服务端主组件） | `hunger.current` 字段 / `GetPercent()` | **`GetCurrent()`**（那是 hunger_replica 客机方法） |
| 实体事件 | `inst:ListenForEvent("itemget", fn)`（事件是 PushEvent 到**实体**的） | `inventory:ListenForEvent`（组件没有这方法） |
| weapon | `SetDamage` `SetRange(min,max)` `SetProjectile` `SetOnProjectileLaunched` `SetOnAttack` | — |
| projectile | `SetSpeed` `SetOnHitFn` `SetOnMissFn` `SetOnThrownFn` `Throw` `Hit` | onhit 里勿重复 DoAttack（Hit 已自动结算） |
| finiteuses | `SetMaxUses` `SetUses` `SetOnFinished` | — |

- **主组件 vs replica 方法集不同**：grep 源码时 `components/xxx.lua`（服务端）和
  `components/xxx_replica.lua`（客机）分开查，查到就信 = 踩坑。
- `AddComponent("name")` 自动从 `scripts/components/name.lua` 加载，无需 require。
- `require` 可用（加载游戏组件安全）；`modimport("scripts/xxx")` 加载 mod 内脚本；
  **`modrequire` 不存在**（裸调必崩）。

### 常量拼写必查 constants.lua

`ANIM_ORIENTATION.BillBoard`（大写 B+D，写 Billboard → nil 崩）。写 `XXX.YYY` 前：
`python scripts/dst_zip_tool.py grep "ANIM_ORIENTATION =" --path-glob "scripts/constants.lua"`。

## 五、字符串/台词规则

```lua
STRINGS.NAMES.MYSWORD = "圣剑"                       -- ✅ NAMES 可裸写
local char = STRINGS.CHARACTERS.GENERIC              -- DESCRIBE 表可能不存在，先判空
if char ~= nil then
    char.DESCRIBE = char.DESCRIBE or {}
    char.DESCRIBE.MYSWORD = "一把锋利的剑"
end
```

- key 用 **大写 prefab 名**（引擎 `string.upper` 查找）；Maxwell=`WAXWELL`、Wigfrid=`WATHGRITHR`、WX-78=`WX78`。
- 角色检查台词注入模板（遍历原表 = 天然跳过 Wes/未装角色）：

```lua
local QUOTES = { GENERIC = "……", WENDY = "……" }  -- GENERIC 就是 Wilson！
for c, tbl in pairs(GLOBAL.STRINGS.CHARACTERS) do
    if QUOTES[c] ~= nil then
        tbl.DESCRIBE = tbl.DESCRIBE or {}
        tbl.DESCRIBE.MYSWORD = QUOTES[c]
    end
end
```

## 六、事件回调 data 参数（高频静默失效点）

- `inventoryitem` 的 `onputininventory` 事件：**data = owner 实体本身**，不是表！
  `data.owner` 恒为 nil → 条件永远 false → 功能静默失效（无报错）。
- `onremovefrominventory` 事件**不存在**（只有 onputininventory / ondropped / onpickup）。
- 摘下装备时回调里拿不到原 owner → 挂载时自己记录引用（`inst._my_owner = owner`）。
- `AddPrefabPostInit` 回调**每次 SpawnPrefab 都执行**（主客两端）→ 访问组件前必须 nil 守卫。

## 七、状态图（StateGraph）速记

- `State{name, tags, onenter, onexit, onupdate, ontimeout, events={EventHandler(...)}, timeline={TimeEvent(n*FRAMES, fn)}}`；
  `tags={"busy"}` = 不可打断；`sg:SetTimeout(t)` 配 ontimeout。
- `AddStategraphState("wilson", state)` 的第一参是 SG 名：**不带 SG 前缀、角色名小写**
  （SGwilson.lua 尾部 `return StateGraph("wilson", ...)`）。写 "SGwilson" 全不生效！
- 动画名必须真实存在（`PlayAnimation("attack")` ✓；不存在的名字 → 透明无报错）。
- 自定义动作 = `AddStategraphState` + `AddStategraphPostInit` 包装
  `sg.actionhandlers[ACTIONS.XXX].deststate`。
