# 锅料理 / 食物 Mod 专项

## 一、注册方式（别混淆两个 API）

```lua
-- 锅料理（烹饪锅产物）：
AddCookerRecipe("cookpot", recipe, true)   -- 三锅：cookpot / portablecookpot / archive_cookpot
-- 制作栏合成（做"食材物品"如菜丸时）：
AddRecipe2("veggie_balls", { Ingredient(...) }, TECH.NONE, {...}, { "INGREDIENTS" })
```

- **recipe 必须带 `weight`**（缺了烹饪直接崩，引擎无 nil 兜底）。
- recipe 表常用字段：`test(ingr, names, cooker)` / `priority` / `weight` / `cooktime` /
  `overridebuild`（锅上贴图 build）/ `cookbook_category="cookpot"` / `potlevel` / `floater`。
- 食材 tag 值：`AddIngredientValues({"ash"}, {inedible = 1})` 让非食材入锅；
  tag 有 `fruit/monster/sweetener/veggie/meat/fish/egg/decoration/fat/dairy/inedible/seed/magic`。

## 二、★★★ FOODTYPE 没有 FISH

`FOODTYPE.FISH` **不存在**（全源码 0 命中）。鱼肉料理一律 `FOODTYPE.MEAT`。
写了 FISH = edible 变 nil = 食物变成只能检视不能吃的摆设。
全成员：`BERRY / BURNT / CORPSE / ELEMENTAL / GEARS / GENERIC / GOODIES / HORRIBLE /
INSECT / LUNAR_SHARDS / MEAT / MIASMA / MONSTER / NITRE / RAW / ROUGHAGE / SEEDS / VEGGIE / WOOD`。

## 三、priority 抢菜机制（新料理必查）

同 priority 会按 weight 随机抢菜。原版高优先级表（定 priority 前必查）：

| priority | 原版料理 |
|---|---|
| 50 | leafymeatsouffle |
| 30 | lobsterbisque / moqueca / dragonchilisalad / potatosouffle / bonesoup / glowberrymousse / ... |
| 26 | leafymeatburger |
| 25 | leafloaf / meatysalad / lobsterdinner |

- 自家料理要稳定出 → priority ≥ 30，且 test 里加排他条件（如 `not names.onion`）避开同档原版菜。
- 改原版料理 test：`local pf = require("preparedfoods"); pf.leafloaf.test = 新函数`。
  **注意同名两文件**：`scripts/preparedfoods.lua` 返回 recipe 表；`scripts/prefabs/preparedfoods.lua`
  返回 Prefab 列表，别 require 错。
- **沃利调味炉铁律**：生食材/非锅料理**禁止加 `preparedfood` tag**——能塞进调味炉但没配
  调味产物 → `SpawnPrefab(nil)` 崩。调味配方数 == spiced prefab 数必须一致（diff 两份 key 清单）。

## 四、食物 prefab 模板（关键行）

```lua
inst:AddComponent("edible")
inst.components.edible.healthvalue = 25      -- 回血
inst.components.edible.hungervalue = 35
inst.components.edible.sanityvalue = 15
inst.components.edible.foodtype = FOODTYPE.MEAT

inst:AddComponent("perishable")
inst.components.perishable:SetPerishTime(10 * 480)   -- 10 天（1天=480秒）
inst.components.perishable:StartPerishing()

inst.AnimState:SetBank("vre_mysdish")        -- 盛在锅里的贴图 build
inst.components.inventoryitem:ChangeImageName("mysdish")  -- 或 imagename
```

- 贴图三步法（缺一步 = 白方块）：rembg 抠图 → 内容 bbox → **bbox 外圈 alpha=0**
  （禁止 alpha=255 白底直接编 tex）。物品栏 64x64 / 锅内动画格约 200x132。
- `displaynamefn` 必须在 SetPristine **之前**设置（客户端要用，晚了 = 名字 MISSING）。

## 五、角色检查台词（17 角色实证规则）

- **Wilson 走 `GENERIC` 表**（原版没有 STRINGS.CHARACTERS.WILSON，写了不显示！）。
- 角色 key 全集（17 个）：`GENERIC(=Wilson) WALTER WANDA WARLY WATHGRITHR WAXWELL WEBBER
  WENDY WICKERBOTTOM WILLOW WINONA WOLFGANG WOODIE WORMWOOD WORTOX WURT WX78`。
- **写了也永远不显示的 key**：`WES`（默剧）/ `WIGFRID`（要用 WATHGRITHR）/ `WILSON`
  （要用 GENERIC）/ `WALANI` 等 DS 单机角色。这些 key 会被**静默跳过不报错**。
- 语气参考（同一道菜官方中文对照）：Wilson 平实 / Warly 厨师爱双关 / Wormwood 质朴只关心
  "填肚子" / Wathgrithr 简短押韵 / WX78 全大写机械 / Wendy 冷淡反讽。
- 注入模板见 `lua-and-prefabs.md` 第五节（遍历 STRINGS.CHARACTERS 原表，天然 nil 守卫）。
- 双语：zh/en 两套 key，modmain 按 `GetLocale()` 分流；**scripts/ 下禁止用 modmain 自定义
  全局（如 Loc）**，用 `TUNING.X = bool` 传语言开关。

## 六、审查/自检清单（食物包专用）

1. 数值多副本一致性：prefab hardcode / recipe 表 / 调味表 / 注释 四处对齐（grep 数值时
   先 `sed 's/--.*//'` 剥注释，否则行尾注释数字混入误报）。
2. `pairs(cooking.recipes.自定义锅 or {})` —— 自定义锅没注册配方时是 nil，裸 pairs 崩。
3. 自定义锅机制：`cooking.recipes` 按 cooker 名分桶 → `AddCookerRecipe("furnace", recipe)`
   = "仅特定配方可入此锅"的官方隔离机制。
4. prefab 名 / bank 名 / 贴图名凡是引用，先验证存在（掉落表写 bank 名 = SpawnLootPrefab 崩）。
5. `SetSharedLootTable` 覆盖原版表名必须放 `AddPrefabPostInit` 钩子里（modmain 顶层会被
   原版加载覆盖）。
6. buff 类食物：`OnDetached` 必须 `RemoveEventCallback` 三件套，否则加成永不消失 + 内存泄漏。
