# 首次开发镜像：兼容实现与已知边界

本轮固定目标为 China HyperOS 3 / Android 15、polaris 6/128。以下均为离线实现，不是首启或硬件通过记录。首次开发 ZIP 已生成，六镜像均通过解压哈希回读；镜像和最终 ZIP 的哈希分别见 `reports/final-images.json`、`reports/development-package.json`。

## VINTF 不靠修改接口版本绕过

A15 Lineage nightly 的 XML schema 为 9，donor 读者为 8。用锁定 AOSP QPR2 schema9 解析器序列化，再用 A15 schema8 解析器读回，比较除根 schema 元数据之外的完整语义。没有降低 HAL、FCM 或 SELinux 版本。工具为 `normalize_vintf.py`、`install_vintf_normalized.py`。

`build_vintf_core.py` 和 `vintf_core_check.cpp` 构建真实 AOSP parser/merger/checkCompatibility；输入覆盖 system/system_ext/product 全部声明/矩阵、最终 vendor XML、真实 4.19.325 与最终 kernel.config，kernel level 假设为 5。双向检查通过，缺失必需 HAL 的负对照被拒绝。代码没有伪造 HIDL metadata 表；链接时剔除未用函数。**范围不包括完整 checkvintf CLI、HIDL inheritance 数据校验、运行时注册和 linker namespace。** 本结果未要求 uname 伪装，因此目前不启用 5.15.221。

## 显示和视频为何成组更换

Lineage A15 polaris 原配套 4.9.337；指定内核视频实际编译分支是 `techpack/video_msmnile`，包含 SDM845_FIX。头文件比较发现 V4L2 控制编号/语义差异，旧 OMX encoder 对 intra-refresh 控制存在真实使用线索。头文件差异不等于每个 binary 都必然调用该接口，未采取全局改 ioctl 编号或空函数补符号。

最终保留 A15 vendor 的基带/无线/策略等基础，成组引入旧 OS4 参考中的 graphics allocator3/4、mapper3/4、composer2.4/QTI composer3、display config/color/postproc、32 位 Codec2 服务及配套 display/codec 库。那些选中的 legacy 服务并非 SDK36 APEX。同步配置 rc、VINTF、file_contexts、文件 xattr、seccomp、属性与 media XML；删除旧 composer/allocator/color/LiveDisplay provider 的启动项及重复声明。

旧 `ppd` 与新 composer 都声明 `pps` socket，因此最终去除旧 ppd 服务及其触发，pps 由新 composer 持有。Codec2 的前台 cpuset 写改为 donor 中真实存在的 `ProcessCapacityHigh` task profile。codec XML 入口从 4.9 OMX 视频切为 c2.qti；不宣告未安装的 Dolby 组件。保留原 OMX 服务及音频能力，不因视频适配删除音频支持。

实机旧系统只读采集的 `/dev/video32`、`/dev/video33` 分别是 venus_dec/venus_enc，system:camera 0660、video_device；`/dev/ion` 为 system:system 0666、ion_device。指定 4.19 的 legacy ION 在 ARM32/64 检查中，五个旧 ioctl 及三个结构尺寸匹配。KGSL/DRM、背光与 Wi-Fi 节点的其余记录见 `hardware-nodes.md`。

选中根 ELF 的缺库/强符号/根版本检查通过。64 位闭包中 `libgraphicsenv` 的 Join 符号在平台 libbase 中实际存在，平面清单会误选 vendor libbase；这仍需要运行 namespace 验证。Codec2 字符串引用的 10 个 C2D2 函数和一个 Adreno 对齐函数在 A15 GPU 库中都有导出，报告仅证明候选导出存在，不证明动态加载/参数 ABI/实际解码可用。

## 系统、设备页面与不支持的硬件

system/product/mi_ext 的设备属性统一到 polaris、MIX 2S；vendor 保留真实 Qualcomm/SDM845。检查了 Settings 的 `MiuiAboutPhoneUtils` 和 `MiuiMyDeviceDetailSettings`：机型取 marketname/model，CPU 云配置键取 DEVICE，离线核心数/频率来自 sysfs，RAM/存储来自硬件/StorageManager。未修改 Settings 签名或用常量伪造可用容量，原 donor build fingerprint 保留为来源信息；实际页面需真机复核。

新增 `polaris.xml`，校正 LCD60Hz、1080×2160、3400mAh、后置指纹/指示灯等，去 AOD/IR/FOD/双频GPS 等不支持的声明。保留 NFC、双卡4G、5GHz Wi-Fi；5GHz Wi-Fi 与 5G 蜂窝不能混淆。去 donor 的五个硬件专用 RRO（挖孔/圆角/屏下指纹资源、Wi-Fi6 开关和 Civi2 认证图），新增自签名、APK v3 签名验证通过的 framework/Settings 纯资源 RRO。未修改签名验证或删除通用指纹/电话框架。

vendor `ro.vendor.radio.5g=0`，默认双卡网络类型为不含 NR 的 22,22；FOD/side fingerprint 属性为 false，真实后置指纹 HAL 保留。不支持的能力入口关闭；支持但未验收的相机、屏幕色彩、小米服务等不能以“不支持”为由删除。并非所有隐藏菜单、云配置和 SystemUI 入口都已真机遍历，运行 UI 验收仍必需。

## 功耗、日志和文件系统

donor 的 miuibooster/perfservice 默认不随 class 启动，删除 donor 对 fstab.default 的重复 swapon 触发；保留 polaris vendor PowerHAL/thermal-engine。修复充电模式启动名称 `vendor.thermal-engine` 与实际 `thermal-engine` 不一致，并删除充电 rc 中关闭 msm_thermal 的写入；不改热保护阈值。尚无待机电流/温升改善的实测结论。

替换 donor 离线日志启动配置，复用已有 kernellog/offlinelog 标签，开发默认仅记录约 5MiB crash 环形日志，tombstone 数量限10。清掉 donor-only logfs/rescue 充电日志挂载。诊断属性精确标注 system_prop；没有常驻 radio 采集或公网上传。

EROFS 的本地增量/rebuild 合并试验出现坏 inode/不支持的布局，**没有用于真实镜像**。最终流程在独立本地 ext4 工作盘用 root 完整提取并保留 uid/gid/mode/xattrs/capabilities，修改后常规 lz4hc/4KiB 重建。四镜像 incompat 位均为 1，在指定内核支持范围内；每个文件内容与 metadata 均经只读 mount 回读比对，fsck 通过。禁止用丢失 Linux metadata 的 NTFS 解包目录重打包。

最终 vendor/boot fstab 完全相同：静态 EROFS 挂载，ext4 /data + 软件 AES-XTS/CTS FBEv2，不用 ICE、不自动 format；原系统实机 /data 是 ext4，未观察到用户目录加密标志，但不能以伪装属性证明密钥迁移安全。首次 A17→A15 按明确清刷处理，recovery 解密另验。

## 未来换到 HyperOS 4

复用方法与工具，不复用本轮“通过”结论：重新锁定 donor/API；检查 APEX minSdk、policy mapping、native namespace/Binder ABI、真实内核/BPF/ION/视频接口；成组替换 provider 并检查服务唯一性；按新包实际 consumer 调整设备属性/RRO。最后重建镜像、回读 metadata、核对实机布局，分开记录首启、硬件、功耗、恢复和解密。只有真实验收后才推进 stable。
