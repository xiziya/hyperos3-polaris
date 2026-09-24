# 移植交接入口

更新：2026-09-25。本文是后续协作者与自动化助手的仓库内上下文；它能随仓库读取，不依赖聊天记忆。

## 当前结论

目标为 MIX 2S / polaris 6/128 的 **中国版 HyperOS 3 / Android 15**。已真实编译纯净内核和 API35 Lights HAL，已生成 boot/vendor 工程候选，已取得现有系统的实机分区与节点读数。**尚无完整可刷 ROM；没有启动、硬件或功耗验收通过结论。**

主线候选使用 Civi 2 国行系统镜像，以及官方 Lineage 22.2 polaris Android 15 vendor/ODM；后者原本配套 4.9.337，不能据同机型就认定兼容指定的 4.19。旧 OS4 vendor 的 SDK36 APEX、202504 SELinux 映射和 Binder 符号问题见兼容文档，现作为历史对照。

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

1. 完成真正按版本、实例及合并矩阵检查的 VINTF 审计。现有名称清单和 FCM5/6 的 4.19 配置条目检查不能代替完整 checkvintf。研究中的 AOSP libvintf host 驱动尚未完成，不标通过。
2. 检查 Android 15 polaris HAL 对指定 4.19 的图形、ION/KGSL、WLAN、音频等 ABI，以及 linker namespace、dlopen、32 位依赖与服务唯一性。
3. 整理系统/product/system_ext 的 polaris 属性与设备资源，接入有界诊断；核对 perf/thermal/millet 是否竞争控制节点。
4. 重新生成与最终 vendor 同步的 boot，确认真实启动链、fstab、数据加密迁移和 recovery/回退方式。
5. 无已知静态致命阻断后才生成保留现有分区表的完整安装包；开发包与稳定验收分开标记。

当前候选尺寸在实机已有静态分区容量以内，**没有发现必须重新 9008 分区的容量理由**。这尚不能证明 recovery 安装路径可用，不能直接套刷机匣旧 rawprogram/flash_all。

详情入口：[兼容实现](compatibility-and-future-ports.md)、[装配记录](integration.md)、[硬件节点](hardware-nodes.md)、[验收门槛](../config/release-gates.json)。后续交接要更新这些文件，列出新的输入 SHA、候选产物 SHA 和未完成项。
