# ROM 工程镜像装配记录

更新：2026-09-25。以下是本地实际生成的中间产物，**不是完整可刷 ROM**。没有运行刷机匣/9008 脚本，没有写入或格式化手机。

## 输入分层

| 层 | 来源与边界 |
|---|---|
| kernel/DTB | 指定 `lineage-23.2_xiaomi` 固定提交，真实 4.19.325，纯净配置；见 `reports/kernel-build.json` |
| 系统 | Civi 2 ziyi `OS3.0.6.0.VLLCNXM` 国行 Android 15；取 system/system_ext/product/mi_ext；不用其硬件 vendor/DTB |
| first-stage init | 同一已校验 donor boot 中的通用静态 A15 init；不使用 donor 内核 |
| 硬件候选 | 官方 `lineage-22.2-20260924-nightly-polaris-signed.zip` vendor/ODM，SDK35、FCM5、policy 202404；原配套内核 4.9.337 |
| 实机布局 | 用户现有 OS4 经刷机匣 9008 安装后的静态布局；已授权 root 只读采集，见 `reports/live-layout.json` |

来源分别锁在 `sources.json`、`integration-sources.json`、`a15-vendor-sources.json`，均在 `config/`。Lineage ZIP SHA256 为 `daa01df26d9679877cdfbe6cc94e493d9ce97899d369074997347eebd9158dd8`；全包 CRC 和展开镜像 SHA 已核对。这不等于完成 OTA 签名链验证。

## 历史候选：旧 OS4 vendor

`tools/integrate_rom.py` 在副本中适配 EROFS fstab、去掉 mi_product 挂载及 formattable、替换 SDK35 灯光服务、修复 Wi-Fi fwpath DAC、移除固定 IRQ7/493 绑核及六个 permissive 域，写入后回读内容/属主/权限/SELinux xattr，并通过 e2fsck。boot 采用 header v1/4096 页、指定内核和 A15 init，回读验证 kernel 和 ramdisk。

`reports/integration-os4-iteration1.json` 对应第一轮候选。它仍有九个 SDK36 APEX、策略及 Binder ABI 阻断，已停止把它作为主线 vendor。报告保留历史状态，不表示这些问题均已修复。

注意：第一轮 boot 的 header 未保留 `cgroup_disable=pressure`，但内核 embedded cmdline 仍包含该项。当前工具已保留原 header 参数，与内核一致，因此重跑的 boot hash 不会等于历史报告。当前并未完成 PSI/cgroup 行为更改，不能宣称这轮带来功耗收益。

## 主线候选：Android 15 polaris vendor

`tools/prepare_a15_policy.py` 对哈希锁定的 202404 CIL 做权限收紧，再与 donor 三个分区的 policy/mapping 一起执行 `secilc -m -M true -G -c 30`。保留 neverallow 检查，不使用 `-N`、permissive 或改策略版本。

去除 userdebug su 交互、atrace debugfs 调试写入，收紧 isolated compute GPU、camera 属性所有者及 Miracast/TV tuner 网络域成员关系，具体规则/次数见 `config/a15-policy-reductions.json`。这些收紧可能影响相机属性或投屏，仍需要运行回归。编译通过证据见 `reports/a15-policy.json`，不等于 enforcing 已在新 ROM 上运行。

`tools/integrate_a15_vendor.py` 实际完成：

1. 仅复制并把本地 vendor 文件系统扩到 768 MiB，未调整手机的 1 GiB vendor 分区。
2. 将原 `/vendor/odm -> /odm` 链接换成目录，合入官方 ODM 的 etc。donor 的 `/odm/etc` 已指向 `/vendor/odm/etc`，避免链接循环和新增分区。ODM CIL 为空，遇非空会拒绝，要求重新审计。
3. 不带入 ODM 中的旧 precompiled policy/hash，使用本轮检查的 split CIL。
4. 安装实机静态布局 fstab 与 Wi-Fi 节点 rc；不挂载/刷写 mi_product，不自动格式化。
5. 成组移除 Lineage 灯光 provider 的二进制、rc、VINTF，加入本项目 API35 灯光 provider 与 file_contexts。
6. 对改动文件逐项回读 SHA、uid/gid、mode、SELinux xattr，最终 e2fsck 检查通过。

生成 `vendor-a15-candidate.img`，805306368 字节，SHA256 **`107c499d2fa390dc29df9bc3fe12150af76da15fd29b8b9440ea75ac83bf4088`**。装配报告见 `reports/integration-a15-vendor1.json`。这个 vendor 没有旧 SDK36 APEX，但并未证明所有服务可启动。

## 如何复现本轮装配

需要 Linux、Python 3.11+、e2fsprogs 的 debugfs/e2fsck/resize2fs、secilc，以及本地已校验镜像与 HAL 构建产物。旧 vendor 路线额外需要锁定的 mkbootimg archive。不要在设备 block path 上运行这些工具。

用 `prepare_a15_policy.py --help` 指定解包后的四组策略目录；输出目录必须为新目录。`--system` 等参数指向各分区的 `etc/selinux`，不是分区根。按配置锁核对产物。

为 `integrate_a15_vendor.py --inputs` 提供本地 JSON，字段必须为 `vendor`、`odm`、`fstab`、`lights`、`plat_pub_versioned.cil`、`vendor_sepolicy.cil`，值为无空格的绝对文件路径；内容 hash 必须匹配 `config/a15-vendor-sources.json`。本轮 fstab 是历史装配脚本由参考包 fstab 生成的副本。供应新包时先更新来源和审计，不能为了绕过检查直接改 hash。

```sh
python3 tools/integrate_a15_vendor.py --inputs private/a15-inputs.json --output /var/tmp/polaris-a15-new
python3 -m unittest discover -s tests -v
```

上述命令只生成候选，不生成 installer；不包含自动下载、设备刷写或完整从源构建整个 vendor。镜像仅保留本地，公开仓库保存自写工具、来源锁和脱敏报告。

## 进入可刷开发包前仍需完成

- 完整 VINTF 版本/instance 与矩阵合并检查，4.9-origin HAL 到指定 4.19 的接口确认。
- linker namespace/dlopen/32 位与 CPU 指令基线；七个 arm64 服务的候选 ELF 检查不能覆盖全部。
- system/system_ext/product 的设备资源、属性、日志 overlay 及功耗控制器对齐。
- Keymaster 3/4 差异、userdata 的真实加密状态与清刷/迁移策略、AVB/引导和可用回退路径。
- 所有最终镜像尺寸/fstab一致性、安装器目标分区与防误写验证。之后由用户进行真机启动与硬件测试。
