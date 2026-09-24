# polaris 6/128 移植记录

## 已知设备信息与边界

本项目目标明确为 **中国版 HyperOS 3 / Android 15**。Android 17 旧包仅供硬件层与分区调查，不改变目标版本。用户选择旧包 OrangeFox 作为候选，调查与独立验收要求见 [recovery.md](recovery.md)。

用户报告：MIX 2S 6 GB / 128 GB、BL 已解锁；现有第三方 Android 17 / OS4 通过 9008 刷入，刷入前硬件正常，USB/ADB 可用。当前开发机 `adb devices` 尚未发现设备。因此分区信息来自用户给定离线包，**不是实机读回结果**。

用户进一步确认：刷机工具是刷机匣，使用刷机匣官方通用 845 引导，再经 9008 刷入。实机的引导、GPT、fstab 必须与包内资料分开核对，不能假定实际运行的是包内 bootloader 或包内 GPT。后续安装器默认保留现有引导，不调用通用 9008 刷写脚本。

现有包的内核字符串显示 5.15.221，IKCONFIG 标题显示 5.15.207。用户已明确说明实际为 4.19、这些版本号是作者伪装；不能据此判定 ABI 或内核世代。实际兼容性以源代码、驱动接口、符号、VINTF/SELinux 和启动实测为准。现有内核配置启用了 KSU，故不能作为本项目的纯净内核产物。

指定内核提交的源码 Makefile 是 4.19.325。SDM845 defconfig 已有 BPF_SYSCALL、BPF_JIT、CGROUP_BPF、BPF_LSM、NET_CLS_BPF、NET_ACT_BPF 等设置，不能按原生老 4.19 推断缺功能。仍须查看 `olddefconfig` 的实际结果及 Android netd/bpfloader verifier 报错，不按版本号盲加补丁。

## China 底包候选

候选：Civi 2 / ziyi，`OS3.0.6.0.VLLCNXM`，Android 15，国行 CN。来源目录由第三方索引发现，文件从小米官方 CDN 下载。`config/sources.json` 保存具体 URL、长度及最终哈希位置。

理由：国行手机完整米系服务、Android 15 路线比 Android 16/17 跨版本改造更少。Civi 2 使用骁龙 7 Gen 1，**不是 SDM845 同平台，也未证明是最容易移植的唯一选择**；其 ARMv8.2 CPU、Adreno、GKI 驱动、分区和 HAL 不能沿用。是否可作为最终 donor 取决于解包后的 bionic/APEX 指令要求、ELF 依赖、系统镜像尺寸和 HAL 合同。845 的硬件层始终使用 polaris 专用实现。骁龙 870 的 12X/普通 Pad 6 不因平台相近就被当作存在官方 HyperOS 3 的底包。

下载实测：bigota/hugeota 不带 Referer 返回 403；增加官网 Referer 后能读取，但 hugeota 四连接约 79 KiB/s。参考 `poposjj/mirom` 的 CDN 路由调查后，直接使用原路径的 `cdnorg.d.miui.com`，TLS 验证保持开启。节点返回长度 6275771344、CRC64 7460013344813003820 与原节点一致，16 连接实测速率约 12 MiB/s。仅研究其下载机制，未执行第三方下载器。完成后检查全包 ZIP CRC、文件名 MD5 前缀并计算 SHA256；MD5 前缀和 HTTPS **不等于已完成 OTA 签名验证**。

## 旧包分区调查

`reports/reference-package.json` 是工具生成的离线报告。原始 XML 和镜像不上传。

| 分区 | 原始 XML 容量（字节） | 调查意义 |
|---|---:|---|
| boot | 67108864 | boot header v1，4 KiB 页，需重新构建纯净 kernel/ramdisk |
| vendor | 1073741824 | polaris HAL 候选，保留依赖整体审计 |
| system | 1717567488 | 独立物理分区 |
| system_ext | 1503657984 | 独立物理分区 |
| product | 5368709120 | LUN 0 中新增 5 GiB，改变 userdata 起点 |
| mi_ext | 270336 | 与稀疏镜像展开尺寸需要单独核对 |
| mi_product | 262144 | 包中镜像展开为 2097152，超出 XML 声明 |

这是自定义静态分区包；参考 Lineage 23.2 的 `system/vendor/cust` retrofit dynamic 布局不能直接使用。fstab 把 `logdump` 用作 `/metadata`，也不能将其视为可随便清理的日志分区。离线包的 XML、GPT 和实机 GPT 可能不一致，需要逐项交叉验证。禁止执行旧包 `flash_all*`：其脚本会写 bootloader/modem、擦除 sec/userdata，且未完整覆盖 product/system_ext 等内容，不能用作新安装器。

不写 modemst1、modemst2、fsg、fsc、persist、persistbak、frp、devinfo、sec、GPT；不触碰 QCN/IMEI。EFS/校准备份只保留用户本地。原厂 modem/BT/DSP 固件也不从 donor 替换。未来若确有必要变更固件或分区，必须有独立的实机布局和恢复方案，不能藏进普通 ROM 安装器。

## 设备树与内核对齐

参考 Lineage `BoardConfigCommon.mk` 引用 `vendor/xiaomi/mi845_defconfig`，但指定内核没有该文件。本项目使用 `vendor/sdm845-perf_defconfig` + `vendor/xiaomi/sdm845-common.config` + `vendor/xiaomi/polaris.config`，最后合入 `kernel/polaris-pure.config`。构建前检查干净工作区、锁定 SHA、合成后的配置；不拉取任何 Root 安装脚本。

polaris 的 D5X、触摸屏、指纹、无线充电、QCA WLAN、DTS/battery/面板配置来自指定内核现有设备支持，不能套用 donor DTS。新设备树尚未完成；参考源码锁定不等于完成设备适配。

当前旧包 vendor 属性自报 SDK 36、FCM target-level 6，带 `mivendor_sdm845_cn` 和 polaris 指纹伪装。不要把改属性数字当作 HAL 修复。需要解包 donor，验证 framework compatibility matrix、设备 manifest、linker namespace、VNDK、32 位兼容库、SEPolicy 映射和各服务实际启动。

| 子系统 | 需对齐/保留的接口 | 真机验收 |
|---|---|---|
| 基带/读卡 | qcrild 双实例、rmt_storage、QMI、radio 1.5 / radio.config 1.1、firmware 挂载、权限/标签 | 原 IMEI 仍可读、双卡冷启动/飞行模式后注册、通话/短信/LTE/IMS |
| Wi-Fi/蓝牙 | 指定内核内建 QCA_CLD_WLAN、WCNSS/CLD 节点、固件和 persist 校准、NL80211、supplicant | 2.4/5 GHz、休眠唤醒、热点、蓝牙与 Wi-Fi 共存 |
| 图形/相机 | SDM845 Adreno/ION/HWC/gralloc/camera HAL，不能覆盖为 ziyi 实现 | 桌面、视频、旋转、相机与通话并行 |
| 存储 | 物理布局、metadata/logdump、FBE、Keymaster/Gatekeeper、init first-stage | 解锁/重启解密、文件读写、恢复路径 |
| 功耗 | polaris thermal-engine、Power HAL、schedutil、cpuset、UFS/低功耗节点 | 深睡、待机、温度、电流、充电与持续负载 |
| 米系服务 | 原签名账号/云服务 APK、privapp 权限、框架依赖、Keystore | 账号登录、联系人/相册同步、推送、主题 |

## 功耗原则

先使 thermal-engine、温控传感器与 Power HAL 正常工作，再根据统计优化。保留电池温控、充电电流保护、热关机；不超频、不关闭温控、不加入狂暴引擎、不强制最低频率，不按 6 GB 内存拍脑袋设置激进 zRAM。多套 perf/thermal/millet 控制器不得抢写节点。

旧包 cmdline 的 `lpm_levels.sleep_disabled=1` 在 init 后有写 0 的路径，不能只看命令行就声称它一直禁止深睡。必须检查启动后的实际值、suspend residency、wakelock 和 screen-off 电流。内核 MSM thermal 开关与 userspace thermal-engine 的接管关系也需要实测，不能盲目删除或反转。

## 日志与使用

`tools/collect_device.py`：只读 ADB 收集，默认不读 IMEI，不自动上传，不提升 root，不重启、不改分区。`--include-logs` 加收有上限的 crash/radio logcat、dmesg、pstore 和 DropBox 索引；因权限缺失读不到的内容保留错误，不假报成功。

```bash
python3 tools/inspect_package.py /path/to/old-package --output work/reference.json
python3 tools/collect_device.py --adb /path/to/adb --output private/device
python3 tools/collect_device.py --adb /path/to/adb --output private/device --include-logs
bash tools/download_donor.sh /path/with/free-space
KERNEL_SOURCE=/linux/kernel KERNEL_OUT=/linux/build CLANG_BIN=/toolchain/bin bash tools/build_kernel.sh
```

纯净配置保留 pstore/ramoops、IKCONFIG 与崩溃排查能力；不改变 ramoops 物理地址。已核对 donor 的 logcatlog rc 和 SELinux 标签，并写出 `device/polaris/diagnostics` overlay：复用已有域与路径，仅 crash、约 5 MiB 轮换、可开关。它尚未集成进 ROM，需验证 enforcing 权限和灭屏功耗；稳定版默认关闭调试模式。tombstones、ANR、DropBox、pstore 作为事件型诊断，日志不进入公开 CI artifact。

## stable 验收

`config/release-gates.json` 当前全部为未验收。至少完成三次冷启动、双卡/数据/通话、Wi-Fi/蓝牙、解密与存储、温控充电与待机、小米账号云同步、恢复回退；先记录基线再对比。NFC 可按用户要求延后，但不能把基带/存储/功耗问题降为可忽略 bug。没有测试证据不得移动 stable 到可刷发布。
