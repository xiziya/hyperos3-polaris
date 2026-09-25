# OrangeFox 候选与 Android 15 验收

## 当前路线：自行编译

用户已决定自行编译适合本项目的 OrangeFox。`recovery/polaris` 是新的静态布局设备树；旧包镜像只保留为对比证据。使用官方 `fox_12.1`（官方文档推荐用于 Android 12 及以后设备），不把 recovery 的编译平台版本当作被恢复 ROM 的 Android 版本。

新树使用本项目从指定源码构建的纯净 4.19 内核；支持 ext4/F2FS/EROFS，但本 ROM 的 userdata 默认明确为 ext4、软件 AES-XTS/CTS FBE v2。QCOM Keymaster 服务、接口声明和构建属性统一为主线 A15 vendor 的 3.0，独立映射 system_ext/product，logdump 仅作为 metadata。移除通用动态分区转换、格式化辅助脚本、Magisk addon 和自动 boot/AVB/加密修改。实机静态布局已只读确认，见 `reports/live-layout.json`；**仍是待编译、待真机验收的开发配置**，不能声称解密已成功，也不能承诺保留旧 Android 17 数据降级。

源码锁见 `config/recovery-sources.json`。标准 Linux CI 工作流 `.github/workflows/recovery.yml` 只由 dev 手动触发；会构建指定内核、同步官方最小源码、记录 Android manifest/补丁和配置，成功时产出明确标为 UNTESTED 的 recovery。构建提交后继续 ROM 本体适配，不等待 recovery 完成；没有自动发布 stable 或刷机步骤。

参考与许可证：设备构建设置参考官方 OrangeFox polaris 与 sdm845-common（GPL-3.0-or-later/上游文件所载许可），保留来源。硬件 HAL 文件在构建时从锁定上游取出，未复制进本仓库。`stage_recovery.py` 限定复制硬件库与三个解密服务，USB rc 沿用上游 4.19 分支。官方说明：https://wiki.orangefox.tech/en/dev/building 。

## 旧包 recovery 调查

2026-09-25 CI 修复：首次运行 [36037703003](https://github.com/xiziya/hyperos3-polaris/actions/runs/36037703003) 已完成纯净内核编译，但在 OrangeFox 同步入口退出。锁定的上游脚本用 `BASE_DIR="$PWD"` 查找 patches；原调用从本工程根目录执行，找错 `patches/patch-manifest-fox_12.1.diff`。`tools/run_recovery_sync.sh` 改为先检查真实 patch，再在 sync checkout 内执行，两个回归测试覆盖异目录调用和缺失 patch 的提前失败。内核配置和 provenance 现在在同步 Android 源码之前保存，即使同步失败也有证据。此修复不等于 recovery 已编译或启动成功。

修复后运行 [36059950820](https://github.com/xiziya/hyperos3-polaris/actions/runs/36059950820) 时，内核和 minimal Android manifest 同步均成功；失败发生在 OrangeFox recovery 源码克隆，GitLab 连续返回 HTTP 503，尚未进入 recovery 编译。新的 CI 会在昂贵内核构建前拉取并校验锁定的 recovery/vendor/common 源码，使用有限退避重试；同步脚本随后从这些已锁定的本地缓存克隆 recovery/vendor，避免同一次构建末尾再次因临时 503 丢失进度。

项目目标是 **HyperOS 3 China / Android 15**。现有 Android 17 移植包中的 unofficial OrangeFox 是用户指定的候选，不等于 Android 17 recovery，也不因 unofficial 标签而直接判定不可用。

## 可复现调查

原镜像来自用户给定旧包的 `images/recovery.img`，67,108,864 字节，SHA256：

`e5eeedfc49f23c02e5315655634d0219b1ccd46cb7eca289c43f0f1946f7e283`

```sh
python3 tools/inspect_recovery.py /path/to/recovery.img --output work/recovery.json
```

工具只读 boot header、gzip/newc ramdisk、IKCONFIG，不执行镜像中的脚本，不挂载、不刷入，不导出其二进制。可核对 `reports/recovery-inspection.json`。

## 已发现的兼容缺口

1. Header v1、4 KiB 页；ramdisk 自报 SDK 32，release 却写成 `99.87.36`。这类属性不能证明 Android 15 FBE 支持，版本标签不能代替实际解密测试。
2. 主 `recovery.fstab` 没有独立 `product`/`system_ext`，静态备用 fstab 把 `cust` 映射到 `system_ext`，与旧包 XML/GPT 的独立物理分区不符。metadata 也不能按通用 SDM845 的 `cust` 假设处理；旧 ROM 把 `logdump` 用作 metadata。
3. `init.recovery.qcom.rc` 启动 `fix_dynamic_static.sh`，它根据 recovery 属性与 system 前 256 KiB 的动态分区标记切换 fstab/flags。因此只改主文件会留下被备用配置覆盖的问题。目标配置、备用配置、选择脚本与 TWRP flags 必须一起对齐实际分区。
4. 主 fstab 声明 ext4/EROFS，但嵌入内核配置未找到启用的 EROFS 选项。配置入口不等于内核实现。需检查 recovery 自身内核和实际 mount；不能用 Android 正常启动时的内核支持替代 recovery 内核。若不支持，优先研究匹配 recovery 的内核重建；转换 donor 镜像为 ext4 还需重新核对展开尺寸、标签、稀疏镜像和分区容量。
5. `/data` 配置是 `fileencryption=ice`，TWRP flags 又声明 `ice:aes-256-cts:aes-256-heh`。需要与最终 Android 15 vold、FBE policy、metadata encryption、Keymaster/Gatekeeper 和现有数据密钥逐项核对。能进入界面、ADB 或刷镜像，都不能证明能解密数据。
6. `factory.sh dynamic` 会格式化 userdata/cache/cust，该布局不适用于当前包；它需要显式参数，离线发现不代表开机自动执行。移植时应禁用不适配的分区重建/格式化菜单，保留普通安装流程之外的显式数据操作边界。

当前结论：**保留为候选，不能原样标记为已适配，也未生成修改后的 recovery。** 没有对手机执行刷写、格式化或重启。

## 验收分开进行

- 引导：在确认实机布局和回退条件后验证显示、触摸、USB/ADB，保存 recovery 内核日志和 recovery.log。
- 挂载/安装：先只读核对真实 by-name 链接、分区容量、fstab、EROFS/ext4、product/system_ext/metadata，再检查安装器允许写入的目标及镜像展开大小。
- 数据解密：分别验证 Android 15 首次使用后的无锁屏/有 PIN 数据，重启后能读数据且系统仍能解锁；Android 17 旧数据跨版本保留是另一个问题，不能以格式化数据冒充解密成功。
- 恢复：确认失败后可进入 recovery/引导模式并回退，不能以现有 9008 工具可用为由直接覆盖引导或 GPT。

未来 HyperOS 4 沿用同样的三个独立结论：能启动、能正确安装、能解密。每项结果必须绑定实际 recovery 哈希、ROM 哈希、分区布局与测试日志。
