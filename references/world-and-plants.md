# 植物 / 树木 / 种植 / 世界生成

## 一、growable 多阶段树（evergreens 同款框架）

```lua
local growth_stages = {
    { name = "sapling", time = function(inst) return 300 end, fn = SetSapling },
    { name = "short",   time = function(inst) return GetRandomWithVariance(525, 75) end, fn = SetShort },
    { name = "normal",  time = function(inst) return GetRandomWithVariance(1800, 300) end, fn = SetNormal },
    { name = "tall",    time = nil_fn, fn = SetTall,
        growfn = function(inst)   -- growfn 属于【目标阶段】：先 SetStage(新) 再调新阶段 growfn
            inst.AnimState:PlayAnimation("grow_normal_to_tall")
            inst.AnimState:PushAnimation("sway1_loop_tall", true)
        end },
}
inst:AddComponent("growable")
inst.components.growable.stages = growth_stages
inst.components.growable:SetStage(1)
inst.components.growable:StartGrowing()
```

- `SetStage(n)` 会调 `stages[n].fn(inst)` → 每阶段 fn 里更新贴图/砍伐次数/掉落。
- `time = nil`（或已是最后阶段）= 不再生长；`time` 用函数返回秒数。
- **★★ GetRandomWithVariance(base, rand) = base ± rand**（要 450~600 必须写 (525, 75)，
  写 (450, 150) 就是 300~600，数值直接偏一倍）。
- 洞穴缩短：`TheWorld:HasTag("cave")` → 时长 ×0.75。

### 树类动画名必须带阶段后缀

palmTree 系动画名 = `idle_short / chop_normal / fallleft_tall / stump_short`（拼接生成）。
写裸名 "chop" → bank 找不到 → **出生就无贴图**。按阶段映射：

```lua
local function StageSuffix(inst)
    local s = inst.components.growable ~= nil and inst.components.growable.stage or 1
    if s <= 2 then return "short" end
    if s == 3 then return "normal" end
    return "tall"
end
inst.AnimState:PlayAnimation("chop_" .. StageSuffix(inst))
```

### 树苗/砍伐/树桩（原版 sapling/evergreens 同款）

- 树苗（stage 1）：交互 = 铲子挖（DIG 1 次）掉树枝。
- 砍伐（stage 2+）：`workable:SetWorkLeft(5/10/15 按阶段)` + `SetOnWorkCallback`。
- 砍倒：播 `fallleft/right_后缀` + `DropLoot(pt ± TheCamera:GetRightVec())` 侧抛 +
  换树桩：`RemoveComponent("workable")` + AddTag("stump") + `growable:StopGrowing()` +
  重建 workable（DIG 1 次）掉 log。

### ★★ SoundEmitter 必加

树/生物 prefab `CreateEntity` 后**必须** `inst.entity:AddSoundEmitter()`——砍树播报音效
缺它直接崩 `attempt to index field 'SoundEmitter' (a nil value)`。

### 守卫召唤 + 防催熟

- 守卫（leif 模式）：只高大阶段 + 天数 ≥3 + 1/75 概率 → SpawnPrefab 守卫 + SuggestTarget + 自身 Remove。
- 防催熟（应用造林学跳过）：加 `ancienttree` tag（原版 SILVICULTURE_CANT_TAGS 现成）。

## 二、种子种植（deployable，pinecone 同款）

```lua
local function ondeploy(inst, pt, deployer)
    local tree = SpawnPrefab("mytree")
    tree.Transform:SetPosition(pt:Get())
    tree.components.growable:SetStage(1)     -- 自然生成默认高大，种植强制树苗
    tree.components.growable:StartGrowing()
    inst:Remove()
end
inst:AddComponent("deployable")
inst.components.deployable:SetDeployMode(DEPLOYMODE.ANYWHERE)
inst.components.deployable.ondeploy = ondeploy
```

- `plantable` 组件**没有** plantfn 字段（用 deployable + ondeploy 才对）。

### 种植间隔 + 几何学 mod 适配

ANYWHERE 模式无种植间隔；要"无地形限制 + 有间隔"必须自定义 CanDeploy：

```lua
inst.components.deployable.CanDeploy = function(self, pt, mouseover, deployer, rot)
    if not self:IsDeployable(deployer) then return false end
    local x, y, z = pt:Get()
    return TheWorld.Map:IsPassableAtPoint(x, y, z)
        and TheWorld.Map:IsDeployPointClear(pt, self.inst, DEPLOYSPACING_RADIUS[DEPLOYSPACING.DEFAULT])
end
-- ★ 双端一致：客户端 replica 走 classified 无间隔 → 必须 AddComponentPostInit("inventoryitem_replica")
--   对同 prefab 做同样 override，否则客户端绿点/服务器拒绝 = 点不动
```

- 几何学 mod 网格：注册 placer `MakePlacer("xxx_seed_placer", bank, build, anim)`
  （单独文件 + PrefabFiles），deploy 时按 `inst.prefab.."_placer"` 自动取用。

## 三、自然生成（精确数量）

```lua
AddRoomPreInit("DeepForest", function(room)   -- fn 收房间定义表，生成前生效
    room.contents.countprefabs = room.contents.countprefabs or {}
    room.contents.countprefabs["mytree"] = function(area) return math.random(2, 4) end
end)
```

- `countprefabs` = 精确数量（值可数字/函数）；`distributeprefabs` = 概率权重（值必须数字）。
- **`AddTaskPreInitAny` 不存在**（只有 AddTaskPreInit / AddTaskSetPreInitAny / AddRoomPreInit）。
- 自然生成默认高大：prefab 默认 `SetStage(4)`，种子种植时 `SetStage(1)` 强制树苗。

## 四、引用验证

prefab 名 / bank 名 / 贴图名凡有引用先验证存在：`moontree_blossom`（物品 prefab）的 bank
叫 `moon_tree_petal` —— 掉落/配方里写 bank 名 = SpawnLootPrefab 崩。

## 五、新地皮（TileManager.AddTile 动态注册）

> 签名与常量已对照官方源码核实：tilemanager.lua:147 / tiledefs.lua:85-89 /
> worldtiledefs.lua:7-13 / constants.lua:811。旧版 tiles.lua/GROUND 常量表已废弃
> （constants.lua 注释 "deprecated, nothing should add into this table"）。

```lua
-- 现代写法：所有地皮由 TileManager.AddTile 动态注册，ID 自动分配进 WORLD_TILES
local AddTile = GLOBAL.require("tilemanager").AddTile   -- 或经 modutil 钩子
AddTile("myturf", GLOBAL.TileRanges.LAND,
    { ground_name = "myturf" },          -- tile_data（新 tile 无 old_static_id，可省略）
    { name = "myturf", texture = ..., noise_texture = ... },  -- ground_tile_def
    { name = "myturf" },                 -- minimap_tile_def
    nil)                                 -- turf_def（可采集地皮物品定义，可选）
```

- **mod 只能在 tiledefs.lua 的 `mod_protect_TileManager = false` 窗口期内调**（该文件
  85→1652 行之间；官方设计即允许 mod 在此窗口注册，越窗直接 assert 崩）。
- **贴图路径自动映射**：`ground_tile_def.name` → `levels/tiles/<name>.tex` 与 `.xml`
  （GroundImage/GroundAtlas，worldtiledefs.lua:7-13）——所以贴图必须放对目录，
  尺寸 1024x1024、tile 图集 2048x1024（128x128 一格）。
- ID 段：`WORLD_TILES_LAND_START = 256`（constants.lua:811），LAND/NOISE/OCEAN/
  IMPASSABLE 各段独立递增；TileGroupManager 按段判断 IsLandTile/IsOceanTile。
- mod 端还有 `env.RegisterTileRange(range_name, start, end)` 钩子（modutil.lua:357）可自定义段。
- **零美术成本技巧**（神话书说/登仙实证）：tile 的 xml 直接引用游戏本体纹理
  `<Texture filename="data/DLC0002/levels/tiles/jungle.tex"/>` 只重排 UV 造"新"地皮。
- 铺设：`TheWorld.Map:SetTile(coords, WORLD_TILES.myturf)`（清 undertile 下层数据）。
