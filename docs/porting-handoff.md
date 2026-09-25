# 移植交接入口

更新：2026-09-25。本文是后续协作者与自动化助手的仓库内上下文；它能随仓库读取，不依赖聊天记忆。

## 当前结论

目标为 MIX 2S / polaris 6/128 的 **中国版 HyperOS 3 / Android 15**。已真实编译纯净内核和 API35 Lights HAL，已装配 boot/vendor/system/system_ext/product/mi_ext 六镜像并逐项离线检查；首次开发 ZIP 已生成，全部镜像通过解压哈希回读。包长 5,596,345,065 字节，完整包哈希见 `reports/development-package.json`。**没有启动、硬件或功耗验收通过结论。**

主线候选使用 Civi 2 国行系统镜像，以及官方 Lineage 22.2 polaris Android 15 vendor/ODM。针对原配套 4.9 的视频控制 ABI，显示/Codec2 已成组改为旧 OS4 参考中与 4.19 配套的 legacy 硬件子系统；未搬 SDK36 APEX 或 202504 policy。参考文件的导入闭包、标签/服务和 VINTF 已检查，但 namespace、ioctl 使用和硬件运行仍待验证，见 `docs/development-integration.md`。

## 固定要求

- `dev` 日常工作；`stable` 稳定发布，当前不移动。公开仓库仅所有者有写权限。
- 内核来源和配置保持纯净，不加入任何 Root 框架。BPF 已有 backport，应逐项验证，避免重复导入。
- 仅在证明确需版本字符串伪装时使用 **5.15.221**；目前 `config/kernel-version-compat.json` 为禁用。
- 基带、原 IMEI 读取、双卡、数据、Wi-Fi、存储、充电温控和小米账号云服务需要真实验收。NFC 可以延后。
- 橙狐构建已独立提交，按用户安排先放一边，继续 ROM 本体；不能把 recovery 构建通过当作解密和回退已通过。
- 用户计划拿完整开发包自行刷机测试，当前没有授权在本轮自动刷写或清数据。

## 已有本地证据

用户已明确给现有 SukiSU 的 Shell 授权，仅用于只读调查。分区容量与节点来自实机；boot/recovery/vbmeta 及 modemst1/modemst2/fsg/fsc/persist 的本地备份，经第二次设备端哈希比对一致。备份位于本机忽略的 `private/`，不上传；换电脑后不能默认这些文件存在。

当前 OS4 的 boot 与给定离线包不同，recovery 一致。属性的 locked/green 与内核命令行 orange 相矛盾，不能只看 getprop 判断 BL。userdata 实际挂载 ext4，但加密属性不足以判定真实 FBE 状态；新 vendor 的 Keymaster 3 与旧包 Keymaster 4 差异仍需验证。

## 接下来从哪里继续

用户最新要求先放宽原 ROM 的 recovery 识别。安装器已核验实际 recovery 服务/进程/fstab，不再要求品牌版本属性，实机通过该项；旧橙狐解压原包超过 4 GB 的 product 镜像哈希通过。r3 包只替换安装器和封装说明，见 `reports/development-package-r3.json`。Data ext4 缺少 encrypt 特性仍阻止安装，真实 userdata 尚未修改；独立维护脚本必须另获机主明确授权。见 `docs/installer-revision-r3.md`。

1. 核对开发 ZIP 最终报告与实际 SHA；若无 `reports/development-package.json`，先完成封装回读。保留静态布局，boot 最后写，不运行旧 9008 分区脚本。
2. VINTF 已用锁定的真实 AOSP libvintf core 进行两向矩阵/版本/实例和真实内核配置检查，并验证缺失必需 HAL 的负对照失败；它不是完整 checkvintf CLI 或运行注册验收。
3. 真机连接恢复后验证 recovery、清刷方案与首启。用户已拔线去充电/休息，本轮不能假装仍有 ADB；也不自动刷写或清数据。
4. 最终 ext4 fstab 使用软件 AES-XTS/CTS FBEv2；A17→A15 初次需用户明确备份/清刷，Keymaster3 与旧4之间不承诺密钥迁移。安装器不格式化，recovery 解密和回退需实测。
5. “设置→我的设备”按 MIX 2S/SDM845 修正；只清理不支持的硬件入口（5G 蜂窝、FOD、AOD/120Hz/挖孔、Wi-Fi6），保留后置指纹/4G/NFC/5GHz Wi-Fi。支持但未适配好的功能继续修，不以“不支持”删除。
6. 橙狐 [36084115031](https://github.com/xiziya/hyperos3-polaris/actions/runs/36084115031) 已通过下载、内核和源码 staging；在 lunch 检查缺失 product image filesystem type 时失败。已补齐独立 vendor/product/system_ext 的类型并关闭对应 Android 镜像构建，真实 Make 检查和两个缺失类型负对照通过；完整 recovery 编译仍待 CI。源码 503 的缓存修复本次已生效。

当前候选尺寸在实机已有静态分区容量以内，**没有发现必须重新 9008 分区的容量理由**。这尚不能证明 recovery 安装路径可用，不能直接套刷机匣旧 rawprogram/flash_all。

详情入口：[兼容实现](compatibility-and-future-ports.md)、[装配记录](integration.md)、[硬件节点](hardware-nodes.md)、[验收门槛](../config/release-gates.json)。后续交接要更新这些文件，列出新的输入 SHA、候选产物 SHA 和未完成项。
