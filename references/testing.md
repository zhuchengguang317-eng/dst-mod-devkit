# 无头测试指南（AI 自测 mod 的完整方法）

## 原理

用 DST 自带的**无界面专用服务器**（`bin/dontstarve_dedicated_server_nullrenderer.exe`）
离线启动一次世界并加载你的 mod，盯日志判定 PASS/FAIL。不进游戏、不需要 Steam 登录、
不需要 cluster_token。能抓约 90% 的"一开游戏就崩"（modinfo 错 / Lua 语法错 / prefab
注册崩 / asset 缺失 / postInit 崩）。

## 流程 A：启动测试（所有 mod 通用）

```bash
python scripts/dst_modtest.py <mod目录> --timeout 180
```

- 工具自动：探测 DST 安装目录（找不到用 `--dst "<安装目录>"`）→ 把 mod 拷进临时目录
  （或直接引用 mods/ 内的）→ 生成一次性离线集群 → 启动 → 判定 → 清理。
- **PASS 判定**（三阶段）：
  1. `LOADING LUA SUCCESS` —— 所有启用 mod 加载无异常（启动级安全）
  2. `Telling Client our new session identifier` —— 世界生成成功
  3. （可选）行为脚本打出 `[MODTEST] SCRIPT_OK`
  且日志无 `LUA ERROR` / `Error loading mod!` / `Error loading file` 等。
- FAIL 时打开工具输出的 `dst_modtest_last_run.log`，搜报错行 → 查 `crash-playbook.md` →
  修 → 重测。**FAIL 没修完不许宣称完成。**
- 多 mod 依赖：`python dst_modtest.py MyMod ItsDependency`（第 2+ 个作为依赖同时启用）。

## 流程 B：定向行为测试（验证逻辑真的跑通）

写一个 Lua 测试脚本，世界加载 10 秒后由临时 runner mod 执行：

```lua
-- test_mysword.lua（在服务器环境执行）
local function ok(tag) print("[MODTEST] " .. tag) end

local sword = SpawnPrefab("mysword")
if sword == nil then error("[MODTEST] spawn failed") end
ok("SPAWN OK")

-- 组件断言
assert(sword.components.weapon ~= nil, "no weapon comp")
ok("WEAPON OK")
assert(sword.components.weapon:GetDamage() > 0, "zero damage")
ok("DAMAGE OK")

-- 动画资源断言
assert(sword.AnimState ~= nil, "no animstate")
ok("ANIM OK")

print("[MODTEST] SCRIPT_OK")   -- ★ 成功标记，工具认这一行
GLOBAL.c_shutdown()            -- ★ 用这个退出；os.exit 在 DST 沙箱里是 nil！
```

```bash
python scripts/dst_modtest.py ./mymod --script test_mysword.lua
```

- 每个预期节点前后打标记，看标记是否全数出现 = 行为链路通。
- 音效/动画播放断言：SpawnPrefab → PlayAnimation/PlaySound → print 标记
  （专用服务器 FMOD 是 nosound，能验证 bank/事件/解码不崩，验证不了听感）。
- 退出码：脚本 error 会带崩服务器 → 工具判 FAIL；进程退出码非 0 是正常的，看日志标记。

## 局限（必须向用户说明）

- 服务器**无渲染无音频输出** → 画面观感（pivot/缩放/位置）、声音听感、客户端渲染
  仍需用户进游戏验收。
- **视觉验收推荐路径**：动画/贴图让用户拖进 **DST Mod Tool**（GUI 预览工具，见
  animation-assets.md 工具链 D）确认 pivot/帧序/层级，再进游戏看实际效果——
  比每次都开游戏快得多。
- **纯客户端崩溃无法复现**（如 149 帧动画客户端启动失败——服务器无头加载完全正常）。
- 客户端 HUD / 输入 / 皮肤预览类功能只能静态审查 + 用户实测。

## 测试后清理三件套（防"不是我 mod 的锅"事故）

1. **杀残留进程**：测试进程可能不退出并占 UDP 10999 端口，导致用户自己开游戏服务器报
   `SOCKET_PORT_ALREADY_IN_USE`：

```bash
tasklist | grep -i dontstarve_dedicated          # 查残留（进程名被截断成 ..._dedicated_serv）
netstat -ano | grep -E ":10999|:11000"           # 找占用端口 PID
MSYS2_ARG_CONV_EXCL='*' taskkill /F /PID <pid>   # git-bash 写法；netstat 有 PID 但 tasklist
                                                 # 查无（幽灵占用）也直接杀，报 SUCCESS 即释放
```

2. **恢复现场**：dst_modtest 默认自动删临时集群和 staged mods；手工 harness 才需要
   恢复 modoverrides.lua、删 `_modtest_*` 副本。
3. **单 shard 端口恒 10999**：改 server.ini/cluster.ini/-port 全部无效，端口被占只能清占用。

## 手工 harness（dst_modtest.py 不可用时的兜底）

1. 集群：`<Documents>/Klei/DoNotStarveTogether/<集群名>/`
   （★ **不带账户号前缀**——客户端才用 `<accountid>/` 子目录，服务器 `-cluster 名` 直达根目录）
   - `cluster.ini`：`[gameplay] game_mode=survival max_players=1` + `[shard] shard_enabled=false`
   - `Master/server.ini`：`[network] port=10999` + `[shard] is_master=true`
   - `Master/modoverrides.lua`：`return { ["mymod"] = { enabled = true, configuration_options = {} } }`
2. 启动：

```bash
cd "<DST>/bin"
./dontstarve_dedicated_server_nullrenderer.exe -offline -console -cluster <集群名> -shard Master
```

3. 判定：`LOADING LUA SUCCESS` + `Registering prefab` 覆盖全部 PrefabFiles + LUA ERROR = 0。
4. 测完杀进程（同上）。
