# 崩溃排雷手册（症状 → 根因 → 修法）

排查总原则：**先看日志再猜**。`Documents/Klei/DoNotStarveTogether/` 下：
`master_server_log.txt`（专用服务器，信息最具体）/ `client_log.txt` / `###_CRASH_###.txt`（看时间戳）/
`backup/`（用户已重启游戏时查这里）。搜 `LUA ERROR` / `Error loading` / `attempt to`。
堆栈里 `../mods/workshop-<id>/...` 的 `<id>` 是创意工坊 mod 目录名（映射到
`<Steam>/steamapps/workshop/content/322330/<id>/`），不是本地 mods 文件夹。

## A. 启动/加载失败（服务器起不来、mod 被禁用）

| 症状/日志 | 根因 | 修法 |
|---|---|---|
| `Error loading file prefabs/xxx` + mod 被 disable | **PrefabFiles 三不一致**：表内字符串 ≠ 文件名 ≠ `Prefab()` 第一参 | 三处强一致（文件名 = return Prefab 第一参 = PrefabFiles 字符串） |
| `attempt to index global 'TheWorld' (a nil value)` @ modmain | **modmain 顶层用了 TheWorld**（世界未创建） | 移到 `AddPrefabPostInit("world", ...)` 或运行时回调里 |
| `variable 'GLOBAL' is not declared` | prefab/组件/widget 里写了 `GLOBAL.` | scripts/ 下裸用引擎全局；`GLOBAL.` 只属于 modmain |
| `variable 'xxx' is not declared` @ scripts/ | 用了 modmain 自定义全局（Loc/L 等 env 变量不跨文件） | 跨文件传值走 `TUNING.*` / `STRINGS.*` / `_G.x` |
| `attempt to index global 'TECH' (a nil value)` @ modmain | 没写 env 元表代理 | modmain 第一行写 env 代理（见 lua-and-prefabs.md） |
| `Could not find an asset matching xxx.xml` | 单文件 cp 进不存在的目录**静默失败** | 整目录 `cp -r`；同步完 find 核对 |
| `not a valid Klei texture` | `Asset("IMAGE", "...png")` | 必须编成 .tex 再声明 |
| `Error loading modinfo.lua` | modinfo 语法/字段错（desc 真实换行等） | 对照 first-mod.md 模板 |
| FROMNUM 刷屏 + 制作栏异常 | 配方 atlas 与 Asset 声明不一致 | 两处路径严格一致 |
| mod 加载了但"功能全无反应" | modmain 与 modoverrides 的 key ≠ 文件夹名 | modoverrides 的 key = mods/ 下文件夹名 |

## B. 实体/物品问题

| 症状 | 根因 | 修法 |
|---|---|---|
| 手持无贴图 | swap 动画名不是 `BUILD_90s_90s`/`BUILD`（写了 idle） | 改 SCML 动画名（见 animation-assets.md） |
| 手持无贴图 | OverrideSymbol 第三参 ≠ build 名 / timeline ≠ build 名 | 三要素统一 `swap_xxx` |
| 手持像牙签 | 画布水平有边距 | 紧凑画布 100% 宽 |
| 地面/物品栏白方块 | 贴图白底 alpha=255 直接编 tex | 抠图三步法，bbox 外圈 alpha=0 |
| 物品栏图标不显示 | imagename 带了 .tex / 与 xml Element 不一致 | 三处一致且不带 .tex |
| `Could not find anim bank` | SetBank 参数 ≠ build.bin 里的 buildname | 解 build.bin 对比（≠ zip 文件名） |
| 出生就无贴图（树类） | 动画名没带阶段后缀（裸写 "chop"） | `chop_ .. StageSuffix(inst)` 拼接 |
| `attempt to index field 'SoundEmitter' (a nil value)` | 实体没加 `inst.entity:AddSoundEmitter()` | CreateEntity 后补上 |
| `attempt to index field 'Physics' (a nil value)` @ projectile | 弹射物没加物理组件 | MakeInventoryPhysics + RemovePhysicsColliders |
| FX 特效客户端"没放大/没发光" | SetScale/SetBloom 写在 SetPristine 之后（本地渲染属性不联网） | 移到 SetPristine 之前的公共区 |
| 掉落/刷新渲染异常 | 缺 MakeInventoryFloatable | 补官方标配 |
| 掉落物写错名 SpawnLootPrefab 崩 | 掉落表写了 bank 名（≠ prefab 名） | 先 ls prefabs/ 验证 |

## C. 运行时 nil / API 错（check_api.py 可拦的）

| 报错 | 根因 | 修法 |
|---|---|---|
| `attempt to call method 'Count' (a nil value)` | inventory 没有 Count() | 用 NumItems / FindItems / ForEachItem |
| `attempt to call method 'SetOnPickUpFn'` | 大小写错 | `SetOnPickupFn`（Pickup） |
| `attempt to call method 'SetMaxSize'` | stackable.maxsize 是属性 | 直接赋值 `maxsize = TUNING.STACK_SIZE_xxx` |
| `attempt to perform arithmetic on field '?' (a nil value)` @ stackable_replica | maxsize 写了非预定义值（999） | 只用 STACK_SIZE_CODES：10/20/40/60/120 |
| `attempt to call method 'GetCurrent' (a nil value)` @ hunger | 服务端组件没有 GetCurrent（那是 replica 的） | 服务端读 `hunger.current` 字段 |
| `SetOrientation on bad self (number expected, got nil)` | 常量拼错（ANIM_ORIENTATION.BillBoard） | grep constants.lua 确认拼写 |
| `attempt to call field 'exit' (a nil value)` | DST 沙箱无 os.exit | 测试脚本用 `GLOBAL.c_shutdown()` |
| `bad argument #1 to 'pairs' (table expected, got nil)` | 自定义锅配方桶为 nil | `pairs(cooking.recipes.xxx or {})` |
| `invalid literal for int()` @ 编译器 | framerate 小数（6.0403） | 整数 fps |
| 功能静默失效（无报错） | 事件 data 参数理解错（onputininventory 的 data = owner 实体非表） | 对照源码 PushEvent 处看 data 真实结构 |
| 功能静默失效 | netvar 写成 `netvar:value(x)`（只读 getter） | 服务端 `:set(x)` |
| 进游戏数值条显示 0 | netvar 构造时没同步初值 | ctor 里赋值触发属性钩子 |
| 客机数值条不动 | netvar 声明在 master_postinit | 移到 common_postinit（两端） |

## D. 食物/料理专项

| 症状 | 根因 | 修法 |
|---|---|---|
| 食物只能检视不能吃 | `FOODTYPE.FISH` 不存在 → edible nil | 用 FOODTYPE.MEAT |
| 烹饪直接崩 | recipe 缺 weight 字段 | 补 weight |
| 放鱼进锅出别的菜 | 同 priority 抢菜（moqueca=30） | priority ≥31 或 test 排他条件 |
| 角色台词不显示 | 写了 WILSON/WIGFRID/WES key | Wilson=GENERIC；Wigfrid=WATHGRITHR；Wes 无台词 |
| 中文名 MISSING | displaynamefn 在 SetPristine 之后 / STRINGS 表判空缺失 | 移到 SetPristine 前 + DESCRIBE 判空 |
| 调味炉崩溃 | 非锅料理加了 preparedfood tag | 撤 tag；调味配方数与产物数 diff 一致 |

## E. 联机/客户端专项

| 症状 | 根因 | 修法 |
|---|---|---|
| 服务端好客户端崩 / 反之 | MOD_RPC 与 CLIENT_MOD_RPC 混用 | 分清方向；S2C 必须带 userid |
| RPC 静默失联 | mod 文件夹名两端不一致（namespace=文件夹名） | 部署名统一 |
| 客户端动画无声无息没影 | 挂载点字段不存在（controls.root）/ Widget 无 .inst | 见 networking.md 第四节 |
| 重连后 HUD 状态错 | net 值没变不触发 dirty | 初始主动同步 + 轮询兜底 |
| buff 加成永不消失 | OnDetached 没清事件回调 | RemoveEventCallback 三件套 |
| 客户端无法启动（无 Lua 报错） | 动画 149 帧超限 / 原生崩溃 | 帧数压到 60 量级；看 client .dmp |

## F. 测试环境专项（不是 mod 的锅）

| 症状 | 根因 | 修法 |
|---|---|---|
| `SOCKET_PORT_ALREADY_IN_USE` | 无头测试残留进程占 10999 | `netstat -ano | grep :10999` → 按 PID `taskkill /F /PID`（git-bash 加 `MSYS2_ARG_CONV_EXCL='*'`） |
| netstat 有 PID 但 tasklist 查无 | 幽灵 UDP 占用 | 直接 taskkill 该 PID，报 SUCCESS 即释放 |
| 测试误报 FAIL | 日志噪音（"Error trying to change cluster setting" 等） | dst_modtest 已过滤；人工看日志时注意区分 |
| 测试副本 mod RPC 失效 | 测试目录改名 | namespace 跟文件夹名，runner 与目标一致 |

## 通用排查心法

1. 语法检查过了 ≠ 没问题：**API 存在性跑 check_api.py**，运行时行为跑 dst_modtest.py。
2. `attempt to index/call ... (a nil value)`：先确认"验证的是主组件还是 replica"，再 grep
   `scripts/components/xxx.lua` 看方法/字段到底叫什么。
3. 静默失效（无报错但功能没发生）：九成是 data 参数结构 / 事件没触发 / 客户端早退守卫。
   从源码 PushEvent 处向下追。
4. 修"走路施法"类时序 bug：BufferedAction 参数是创建时快照，从创建点往下追。
5. 改 Lua 不用重编美术；改 PNG 必须重编 anim zip；改 anim 先删旧 zip 防假 "up to date"。
