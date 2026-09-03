# 发布前自检清单

## 代码正确性

- [ ] `PrefabFiles` 三一致：表内字符串 = 文件名 = `Prefab()` 第一参
- [ ] 全项目 grep 确认：scripts/ 下 0 个 `GLOBAL.`；modmain 有 env 元表代理
- [ ] 全项目 grep 确认：0 个 `pcall`/`xpcall`/`dofile`/`loadstring`（注释里也不许）
- [ ] modmain 顶层 0 个 `TheWorld`
- [ ] 每个 `AddComponent` 的方法调用都过过 `check_api.py`（或 grep 源码验证过）
- [ ] netvar：声明在两端（common_postinit）、`:set()` 写入、dirty 事件名与变量名对应
- [ ] 事件回调 data 参数对照源码验证过（onputininventory 的 data = owner 实体）
- [ ] 存档：OnSave 返回表（非参数赋值）、OnLoad 有 nil 防护
- [ ] STRINGS：DESCRIBE 判空；台词 key 用 17 角色实证表（Wilson=GENERIC）

## 资产

- [ ] 所有 anim zip：build.bin + anim.bin + atlas-*.tex 三件齐全（namelist 打印核对过）
- [ ] SetBank 参数 = build.bin 内 buildname
- [ ] swap build：动画名 BUILD_90s_90s/BUILD；folder=build=symbol 三要素一致；细长武器紧凑画布
- [ ] `Asset("IMAGE", ...)` 全部 .tex；imagename/xml Element/RegisterInventoryItemAtlas 三处一致不带 .tex
- [ ] 贴图无白底白方块（bbox 外圈 alpha=0）
- [ ] 动画帧数 ≤ 60 帧量级
- [ ] modicon 128×128（modinfo 的 icon_atlas/icon）

## 数值一致性（多副本是事故重灾区）

- [ ] 同一数值只维护一处；多处出现时 diff + 逐项对照
- [ ] 食物：prefab hardcode = recipe 表 = 调味表 = 注释
- [ ] 锅料理 priority 查过原版高优先级表，test 有排他条件
- [ ] GetRandomWithVariance 语义核对（base±rand，不是 min,max）

## 功能验证

- [ ] `dst_modtest.py` 流程 A PASS（贴 PASS 日志关键行）
- [ ] 核心行为有流程 B 断言（spawn/组件/数值/动画）
- [ ] 测试残留进程已清理（10999 端口已释放）
- [ ] 向用户声明无头测试边界（画面/音效/纯客户端崩溃需真人验收）

## 打包与发布（Steam Workshop）

- [ ] modinfo：name/description（\n 转义）/author/version/api_version=10/dst_compatible
- [ ] all_clients_require_mod 与代码形态一致（内容 mod 必须 true）
- [ ] configuration_options 都有 default；GetModConfigData 有 nil 兜底
- [ ] 用官方 Mod Uploader 上传；版本号 bump + 更新说明
- [ ] 多目录分发（源目录/本地 mods/ workshop content）同步后 md5 核对
- [ ] 英文模式检查：双语表 key 集合 diff（`comm -23` 中文表 key 减英文表 key = 缺失清单）
