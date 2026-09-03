# 联机同步 / RPC / hook 原版

## 一、Replica 组件（客机拿服务端数据的标准姿势）

组件在主机处理，客机 `inst.components.X` 取不到 → 写 `X_replica.lua`：

```lua
-- scripts/components/dest_replica.lua（命名 = 主组件名 + _replica）
local Dest = Class(function(self, inst)
    self.inst = inst
    self._dest = net_string(inst.GUID, "dest._dest", "destdirty")
    if not TheWorld.ismastersim then
        inst:ListenForEvent("destdirty", function(inst) self:OnDestDirty(inst) end)
    end
end)
function Dest:SetDest(dest)
    if TheWorld.ismastersim then self._dest:set(dest) end  -- set() 自动触发 dirty 事件
end
```

- 主组件数据变化时调 `inst.replica.dest:SetDest(self.dest)` 同步。
- **写完必须 `AddReplicableComponent("dest")` 注册**，否则不生效。
- netvar 十类型：`net_bool / net_string / net_entity / net_ushortint / net_byte /
  net_tinybyte / net_smallbyte / net_float / net_event / net_smallbytearray`。
- `:set()` 值没变不触发事件；RPC/net 异步 → 发完立刻读 replica 取不到。

## 二、RPC 双向通信

```lua
-- 客户端 → 服务端
AddModRPCHandler("modname", "reborn", function(player, data) end)   -- 第一参固定玩家
SendModRPCToServer(MOD_RPC["modname"]["reborn"], data)

-- 服务端 → 客户端（★必须带 userid）
AddClientModRPCHandler("modname", "s2c", function(player, str) end)
SendModRPCToClient(CLIENT_MOD_RPC["modname"]["s2c"], player.userid, str)

-- 跨世界（地上↔洞穴）：AddShardModRPCHandler + SendModRPCToShard
```

- `MOD_RPC` 与 `CLIENT_MOD_RPC` 别混；服务端事件客户端收不到（反之亦然）。
- RPC namespace = **mod 文件夹名** → 测试副本改名/部署改名不一致 = RPC 静默失联。
- 服务端权威：客户端传来的坐标/参数在 RPC handler 里**再验一次**（可被改）。
- 专用服务器无 UI：客户端交互入口一律 `if TheNet:IsDedicated() then return end`。

## 三、hook 方法论（改原版行为的万能套路）

```
① 拿到原函数 → ② 包一层新函数 → ③ 条件判断后决定调不调原函数
```

```lua
AddComponentPostInit("sleepingbaguser", function(self)
    local OldSleepTick = self.SleepTick
    self.SleepTick = function(cmp, ...) OldSleepTick(cmp, ...); --[[附加逻辑]] end
end)
```

- **self 坑**：原函数用 self，新函数调用旧函数必须显式传（`oldFn(self, a, b)`）。
- 改动作：直接包 `GLOBAL.ACTIONS.STEAL.fn`（加条件 → return false）。
- 改别人封死的内部函数：`debug.getupvalue(f, i)` / `debug.setupvalue(f, i, newfn)`。
- 钩子选型：`AddPrefabPostInit` / `AddPrefabPostInitAny` / `AddPlayerPostInit` /
  `AddComponentPostInit` / `AddClassPostConstruct`（改 widget/screen 类）/ `AddStategraphPostInit`。
- 整段复制官方大文件 ❌；窄 hook ✅。

## 四、客户端 HUD（widget）专项

- 挂载点：`player.HUD.controls.root` **不存在**（只有 containerroot/topright_root 等）；
  取 nil 静默 return、零报错。对齐物品栏挂 `widgets/inventorybar` 的 self。
- **Widget 没有 `.inst` 字段**（EntityScript 才有）→ `img.inst:DoPeriodicTask` = nil 崩；
  定时任务挂 player 实体，回调里 `if img.parent == nil then return end` 判 widget 死活。
- 动画与 RPC 竞态：服务端同一瞬间 Remove 物品 → 客户端延时回调里实体已失效。
  **点击瞬间抓纯数据**（`GetAtlas()/GetImage()` 字符串），延时回调只用字符串建 Image。
- 移动动画 `Widget:MoveTo(from, to, time, fn)`；渐隐 `Image:SetTint(r,g,b,a)`。
- 世界→屏幕：`local sx, sy = TheSim:GetScreenPos(x, y, z)`（左下角原点）→
  直接 `widget:SetPosition(sx, sy)`，**不要做任何换算**（网上"减半屏"公式是错的）。
  挂载层 `player.HUD.overlayroot`；每帧重算可跟随镜头。
- 物品图标喂 Image：`item.replica.inventoryitem:GetAtlas()/GetImage()`。
- 排查特征：客户端"没显示 + 日志无 LUA ERROR" = 静默 return，先逐行 grep 源码核对
  待挂载字段是否真实存在。

## 五、buff / debuff 模式

```lua
-- buff = 服务端 prefab（CLASSIFIED 标签 + debuff 组件）
inst:AddComponent("debuff")
inst.components.debuff:SetAttachedFn(OnAttached)   -- SetParent + DoPeriodicTask
inst.components.debuff:SetDetachedFn(inst.Remove)
-- 施加：target.components.debuffable:AddDebuff("buffname", "buffname")
```

- 监听 `newcombattarget` 等事件后，**OnDetached 必须 RemoveEventCallback 三件套**，
  否则加成永不消失 + 对已删除实体注册 onremove = 内存泄漏。
- 客户端效果只在 dirty 事件里应用 → 掉线重连后不同步（net 值没变不触发 dirty）→ 初始同步一次。
- 简单加成：timer 组件 + `combat.externaldamagemultipliers:SetModifier(名, 倍率)`。
- 死亡/复活（服务端）：`ms_becameghost` / `respawnfromghost` 事件。

## 六、组件存档

- 签名是**返回值式**：`OnSave() return {...}` / `OnLoad(data)`（写成给 data 参数赋值 = 存不上）。
- 嵌套存档、跨版本迁移用 `OnPreLoad` / `OnLoadPostPass` / `LongUpdate`。
- 本地配置存盘：`TheSim:SetPersistentString` + `json.encode`（读取侧 json.decode 加 nil 防护）。
