# 物品 / 武器 / 投掷 / 弓 / 配方

## 一、物品通用组件包（掉落渲染正常的最小集）

```lua
MakeInventoryPhysics(inst)
MakeInventoryFloatable(inst, "med", 0.05, {1.1, 0.5, 1.1}, true, -9)   -- 少了 → 掉水渲染异常
inst:AddComponent("inventoryitem")
inst.components.inventoryitem.imagename = "mysword"   -- ★ 不带 .tex；与 prefab 名一致最稳
```

- 可堆叠：`inst:AddComponent("stackable")` + `maxsize = TUNING.STACK_SIZE_MEDITEM`（20）。
  只能用预定义值：`STACK_SIZE_LARGEITEM=10 / MEDITEM=20 / SMALLITEM=40 / TINYITEM=60 / PELLET=120`。
- 耐久：`finiteuses`（SetMaxUses/SetUses/SetOnFinished）。
- 可检查：`inspectable`。可作祟：`MakeHauntableLaunch(inst)`。
- 物品栏贴图不显示：`imagename` 与 xml Element name 与 `RegisterInventoryItemAtlas` 第二参
  三处一致、都不带 `.tex`。

## 二、武器本体（近战）

```lua
inst:AddComponent("weapon")
inst.components.weapon:SetDamage(TUNING.MYSWORD_DAMAGE)
```

- 装备换手持贴图（OnEquip/OnUnequip）：

```lua
owner.AnimState:OverrideSymbol("swap_object", "swap_mysword", "swap_mysword")
owner.AnimState:Show("ARM_carry"); owner.AnimState:Hide("ARM_normal")
-- OnUnequip 反向：ClearOverrideSymbol("swap_object") + Show("ARM_normal")
```

  - **不要加 `AddOverrideBuild`**（新版 DST 会干扰 swap 显示）。第三参 = swap build 内符号名 = build 名。
- 官方增伤/位面伤害（voidcloth_scythe 同款）：

```lua
local pd = inst:AddComponent("planardamage"); pd:SetBaseDamage(38)          -- 位面（无视护甲）
local dtb = inst:AddComponent("damagetypebonus")
dtb:AddBonus("shadow_aligned", inst, 0.1)   -- 对暗影阵营 +10%（lunar_aligned=天体阵营）
```

- 冷却（官方组件，UI 自动倒计时）：`inst:AddTag("rechargeable")` +
  `AddComponent("rechargeable")` + `:Discharge(20)`。
- AOE：`weapon.onattack` 里 `TheSim:FindEntities(x,y,z, 4, {"_combat"}, {"INLIMBO","companion","wall"})`
  逐个 `GetAttacked`，自己发 `PushEvent("onareaattackother", ...)`。
- 击飞：`other:PushEvent("knockback", { knocker = inst, radius = 200, strengthmult = 1 })`。

## 三、投掷武器全链路（Action → Stategraph → Projectile）

1. **弹射物 prefab 必带物理**：`MakeInventoryPhysics(inst)` + `RemovePhysicsColliders(inst)`
   （漏了 → `attempt to index field 'Physics' (a nil value)` 崩）；四方向 `SetFourFaced()`。
2. **伤害在弹射物上**（原版 slingshotammo 同款）：

```lua
inst:AddComponent("weapon")
inst.components.weapon:SetDamage(def.damage)
inst:AddComponent("projectile")
inst.components.projectile:SetSpeed(25)
inst.components.projectile:SetOnHitFn(OnHit)      -- OnHit 里 Remove 自己；勿重复 DoAttack
inst.components.projectile:SetOnMissFn(OnMiss)
inst.components.projectile.has_damage_set = true  -- ★ 原版弹药标志，防二次结算
```

3. 投掷动作挂 inst：`inst.my_can_throw = CanThrow` 必须 **SetPristine 之前**（客户端要读）。
4. 借用原版投射物 bank 时 bank 名必须真实存在（如 `blow_dart`），不能拿自己的 swap zip 当 bank。
5. 追"走路施法/发射"类 bug：BufferedAction 的 distance 是**创建时快照**，AOE 距离闸门是
   `aoetargeting:GetRange()`，不是 `ACTIONS.CASTAOE.distance`。

## 四、弓箭/远程（容器弹药架构，弹弓同源）

- **弓 = 容器（弹药栏）+ 武器（空 projectile）**：

```lua
inst.components.weapon:SetDamage(0)                       -- 伤害在弹射物上
inst.components.weapon:SetRange(10, 15)
inst.components.weapon:SetOnProjectileLaunched(OnLaunched) -- 消耗弹药
inst:AddComponent("container")
inst.components.container:WidgetSetup("mymod_bow")        -- 名字在 modmain 注册
inst.components.container.canbeopened = false
inst:ListenForEvent("itemget",  function(inst, data) inst.components.weapon:SetProjectile(data.item.prefab.."_proj") end)
inst:ListenForEvent("itemlose", function(inst)       inst.components.weapon:SetProjectile(nil) end)
```

- 客户端必须 `OnEntityReplicated` 里 `inst.replica.container:WidgetSetup("mymod_bow")`（漏了客户端容器显示异常）。
- modmain 注册容器（`require("containers")` 拿 params 表加自己的键；槽位底图用原版
  `slingshot_ammo_slot.tex`；`itemtestfn` 限制只收箭；大容器要更新 `containers.MAXITEMSLOTS`）。
- **箭头 = 原版弹药协议**：`AddTag("arrow")` + `AddTag("reloaditem_ammo")` +
  `AddComponent("reloaditem")` + stackable → 右键装弹动作自动可用。
- 多箭种数据驱动：箭种表 `{name, symbol, damage, onhit}` 循环生成物品+弹射物 prefab；
  箭头物品共用 bank/build，`OverrideSymbol("normal", "arrow", v.symbol)` 换头。
- 完全自定义拉弓动画走 `AddStategraphState("wilson", ...)` + `AddStategraphPostInit`
  包装 `deststate`（只蹭 slingshot tag 的话拉弓动画是原版弹弓的）。

## 五、配方与科技

```lua
-- 现代 API（推荐）
AddRecipe2("mysword", { Ingredient("twigs", 2) }, TECH.SCIENCE_TWO,
    { atlas = "images/inventoryimages/mysword.xml", image = "mysword.tex" },
    { "WEAPONS", "MAGIC" })
-- 自定义制作栏 tab（官方 AddRecipeFilter）
AddRecipeFilter({ name = "MYTAB", atlas = "images/inventoryimages/mysword.xml",
    image = "mysword.tex", image_size = 64 })
STRINGS.UI.CRAFTING_FILTERS.MYTAB = "我的分类"
AddRecipe2("xxx", {...}, TECH.NONE, {...}, { "MYTAB" })
```

- **配方 atlas 必须与 prefab Asset 声明一致**，否则 FROMNUM 刷屏 + 制作栏连锁崩。
- 老九参 `AddRecipe(name, ings, tab, level, nil,nil,nil,nil,nil, atlas, image)` 仍可用。
- 角色限持武器：`equippable.restrictedtag` 门控（角色挂 tag + 武器限 tag，零耦合）。
- 材料 prefab 名先查证：中文名 → 官方 wiki（dontstarve.wiki.gg）→ prefab id；
  **官方中文 ≠ 字面翻译**（Horror Fuel=纯粹恐惧=horrorfuel），查不到直接问用户。

## 六、修复机制三选型

| 方式 | 写法 | 适合 |
|---|---|---|
| repairable | `AddComponent("repairable")` + `repairer` 物品组件 + `repairable.repairmaterial = "swords"` | 武器耐久修复 |
| trader | `AddComponent("trader")` + `SetAcceptTest` + `onaccept` | 以物易物 |
| forge | 复用原版锻造台协议 | 高级装备 |

## 七、mod 皮肤接入官方系统（Vista Skins API 要点）

1. `CreatePrefabSkin` 会取全局 `_G[base_prefab.."_clear_fn"]` → 先定义全局 clear_fn。
2. 皮肤 prefab 注册 = prefab 文件 return 列表（modmain 里 RegisterPrefabs 不生效）。
3. 换肤生效必须 hook 两个引擎函数：`GLOBAL.SpawnPrefab`（skinid 置 0）和
   `GLOBAL.Sim.ReskinEntity`（先 clear_fn 再引擎调用再 init_fn + 记录 skinname/skin_id）。
4. prefab 文件写全局用 `_G.x = ...`（`GLOBAL.` 崩）。
5. 装备四条路径都要按 skinname 取 build：手持(SWAP)/投掷(FLY)/回收(GROUND)/地面，漏一条 =
   "某状态下贴图不跟皮肤"。
