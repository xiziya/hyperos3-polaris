# ROM 驱动节点与硬件服务对齐

此处讨论的是 **HyperOS 3 China / Android 15 ROM**。`config/node-contracts.json` 记录生产节点的内核源码、HAL 消费方、权限和当前状态；不以同名节点就认定 ioctl、SELinux 或运行时行为兼容。

## 显示、背光、GPU、触摸

指定内核 SDE/DSI 在 `sde_connector.c` 注册 `panel%u-backlight`。polaris JDI、EBBG 两种 DTS 都声明亮度最大值 4095；旧 vendor init 的 panel0-backlight 路径与之对应。不能套用 Civi 2 的面板参数、HBM、刷新率、触摸节点或亮度曲线，也不能把 framework 的归一化亮度直接写成 4095 来代替 Lights HAL 的转换。

主 `.config` 中 `CONFIG_DRM_MSM` 没启用不等于没有显示驱动：这个内核 SDM845 的 techpack Makefile 会导入 `konadisp.conf`，另行开启 DRM_MSM/SDE/DSI；本次构建实际生成 SDE 对象和 polaris DTB。GPU 则启用了 QCOM_KGSL，注册名为 kgsl-3d0。保留 SDM845 的图形 HAL 和 Adreno 库，继续核对 DRM/KGSL/ION ioctl 与 gralloc、composer、EGL 依赖。

触摸包含 polaris 的 Synaptics force 驱动与设备 DTS。真实面板/触控批次、input/event 编号、唤醒路径需按实机枚举，不固定 event 编号，不从 donor 引入触控参数。ADB 收集器已增加只读 input 设备、中断和显示节点权限调查。

## Wi-Fi

实际配置为 `QCA_CLD_WLAN=y`、`ICNSS=y`、`ICNSS_QMI=y`，不是需要照搬另一 SoC 的 CNSS2 模块。源码注册 `/dev/wlan`，旧 libwifi-hal 有同一路径，已有 ueventd 权限为 wifi:wifi 0660。MSM_PLATFORM 编译路径请求 `wlan/qca_cld/WCNSS_qcom_cfg.ini` 和 `wlan_mac.bin`，旧 vendor 中对应 symlink 分别指向自身配置与 `/mnt/vendor/persist/wlan_mac.bin`，这两项已有对应关系，不能用 donor 的校准/MAC 文件覆盖。

HAL 还使用 `/sys/module/wlan/parameters/fwpath`；内核默认 0644，HAL 身份是 wifi，旧 vendor init/ueventd 没找到该节点授权。已写出限定为 wifi:wifi 0660 的 init overlay。donor 平台策略已有 `sysfs_wlan_fwpath` 的 genfscon 和 hal_wifi 写权限，未添加通用 sysfs 放权。此修改仍需完整策略重建后在 enforcing 下验证 STA、热点和恢复休眠。

## 开机与功耗

旧 post-boot 脚本把 IRQ 7 标为 msm_drm、493 标为 kgsl-3d0 并强制绑核；不同内核的 Linux IRQ 编号不能这样继承。生成的 overlay 删除这两项调优，保留内核默认亲和性及 `vendor.post_boot.parsed=1`，避免 perf HAL 一直拒绝请求。未来若测量证明需要 IRQ 调优，应按实际 action 名和 CPU 拓扑验证；不使用旧编号，也不未经测量就改温控或最低频率。

## 历史 OS4 vendor 的硬件服务阻断

`reports/vendor-apex-audit.json` 显示旧 vendor 的 10 个 APEX 全部要求最低 SDK **36**，目标 Android 15 是 **35**。包括 lights、health、power、thermal、perf2、vibrator、memtrack、IPA、boot、devicelvl。不能靠降低 manifest minSdk、换 APEX 签名、提高系统 SDK 属性或搬用 donor SoC 的 HAL 解决。需要选择 SDK35 兼容的 polaris 实现/从相应源码重建，并核对其节点、AIDL/HIDL 版本、动态库和 SELinux。

因此当前还不能保证基带、Wi-Fi、功耗等已正常；节点调查和 staged overlay 是已完成的工程步骤，服务运行和真机验收仍未完成。每项修改需按“驱动源码 → 消费方 → DAC/SELinux → 启动日志 → 功能/功耗回归”记录，未来 OS4 沿用这个流程。

## 已构建的 Android 15 灯光候选

已使用锁定的 Lineage Android 15 Lights 源码、ILights V2 API 和 NDK r27c 构建 API35 arm64 服务。它按 `max_brightness` 转换亮度，真实上游转换代码的 512 个输入检查通过。可重复构建工具、init/VINTF/file_contexts 候选文件与许可证齐备，详情见 [lights-hal.md](lights-hal.md)。服务已在两轮 vendor 工程副本中成组替换：历史 OS4 候选移除了旧 lights APEX，主线 A15 候选移除了原 Lineage lights provider。均未真机运行。

旧策略中 `sysfs_backlight` 与 `vendor_sysfs_graphics` 的授权不同；需要实机背光 symlink 的真实路径和标签来决定精确规则。本轮已取得当前 OS4 实机标签，详见下面记录；新纯净内核 + A15 ROM 下仍需重新验证，没有将整个 sysfs 设为可写，也没有绕过 SELinux。

## Wi-Fi 与基带 ELF 调查

`reports/elf-audit.json` 调查 Wi-Fi、composer、allocator、qcrild 和 rmt_storage 的候选依赖闭包。库名存在不代表 ABI 一致：旧 `android.hardware.wifi-V3-ndk.so` 和 `android.system.keystore2-V1-ndk.so` 导入目标 A15 Binder 库没有的 `AIBinder_Class_setTransactionCodeToFunctionNameMap`。下一步是按 A15 生成并重编对应接口/服务，不能添加空函数掩盖问题。

composer 的某些同名库候选还存在 namespace 歧义，工具结果不是实际 linker 判决。基带的原 IMEI、双卡和数据业务只有在 polaris modem/EFS 保留、服务启动和真实 SIM 测试后才能确认。


## 2026-09-25 实机读数与 A15 路线

用户授权现有 Shell root 后完成只读采集，摘要见 `reports/live-node-contracts.json`：

- 背光真实路径为 `/sys/devices/platform/soc/ae00000.qcom,mdss_mdp/backlight/panel0-backlight`，brightness 为 system:system 0644，标签 `vendor_sysfs_graphics`，max_brightness=4095。
- white LED 最大值4，标签同为 `vendor_sysfs_graphics`。不能把背光4095的范围套到指示灯。
- Wi-Fi fwpath 为 root:root 0644、`sysfs_wlan_fwpath`；`/dev/wlan` 为 wifi:wifi 0660、`vendor_wlan_device`，支持对 fwpath 做限定授权的诊断依据。
- KGSL/DRM节点存在；当前 `sleep_disabled=N`、`mem_sleep=s2idle [deep]`，不能宣称现系统持续关闭深睡。

这些数据来自当前第三方 OS4，并非我们候选 ROM 的验收。A15 vendor 的 Wi-Fi、composer、Keymaster、health、power、qcrild、rmt_storage 七个服务的候选 ELF 检查未发现缺库/强符号/根版本需求问题，见 `reports/a15-elf-audit.json`；这不涵盖 namespace、dlopen、32位或 ioctl。

后续应以新候选实际 rc/ueventd/genfscon 和4.19源码逐项对齐；历史 IRQ 补丁只适用于它锁定的旧 post-boot 输入，不能声称已经修改所有 A15 的功耗脚本。真机至少检查亮度/灭屏唤醒、白灯、STA/热点/共存、触摸/GPU、温控与深睡。
