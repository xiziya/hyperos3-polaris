# 兼容性实现记录与未来 HyperOS 4 迁移方法

本文区分实际完成的实现与后续必须完成的验证。当前没有宣称已实现可启动的 HyperOS 3 ROM。

## 本轮已实现的内容

### 可追溯来源和分支

`dev` 是默认开发分支，`stable` 是稳定入口，目前只保留初始化说明。两分支禁止 force push 和删除。仓库公开，写入协作者只有 xiziya，Actions token 默认只读。CODEOWNERS 只是审阅归属，写权限来自 GitHub 协作者设置，不把 CODEOWNERS 当访问控制。

锁定指定内核 SHA、两份 Lineage 设备参考源码 SHA、Clang 工具链 SHA 和国行 donor SHA256，避免上游分支漂移。完整 donor 已通过 ZIP CRC、文件名 MD5 前缀和 OTA metadata 检查；四个解出的系统镜像分别与 payload 的 SHA256 比对通过。未声称完成厂商 OTA 签名链验证。

### 内核设备配置对齐

指定源码中没有参考设备树要求的 `mi845_defconfig`，因此构建脚本实际依次执行 SDM845 perf defconfig、SDM845 common fragment、polaris/D5X fragment，再加入纯净与诊断 fragment。`olddefconfig` 之后检查 WLAN、文件系统、Binder、BPF 和 pstore，避免只写进片段却因依赖没有进入最终配置。

保留指定内核已有的 BPF/backport，未额外导入所谓 Android 新版通用 BPF 补丁。已核实最终配置包含 BPF syscall/JIT、cgroup BPF、NET_CLS_BPF、NET_ACT_BPF；是否满足新 ROM 每一个 program type/helper/map/verifier 特性仍是运行时检查项目。

纯净检查拒绝任意启用的 KSU/KERNELSU/SukiSU/SUSFS/KPM/APatch 配置。没有执行 Root 安装器，没有移植旧包 KSU。pstore、IKCONFIG 仅用于排查，不赋予应用 Root 权限。

### TAS2557 构建修复与 ABI 保持

指定内核现已完成真实编译，产物 `Image.gz-dtb` 哈希见 `reports/kernel-build.json`；内嵌 IKCONFIG 与构建配置一致，源码补丁退出后恢复干净。仅内核构建通过，尚未生成可启动 ROM，也没有内核真机通过结论。

实际编译发现 `TAS2557_MAGIC_NUMBER=0x32353537` 经 `_IOWR` 左移 8 位时发生 signed overflow，被 Clang 12 作为错误。补丁只把字面量改为 `0x32353537U`，让已有 32 位 ioctl 编号的截断行为变为定义明确的无符号运算；没有把 magic 缩成 8 位，没有改 ioctl 编号、参数类型或音频逻辑。

`tools/check_audio_ioctl_abi.py` 分别交叉编译 ARM32、ARM64 的旧/新头文件，将 `.rodata` 中 8 个 ioctl 常量逐字节对比。结果见 `reports/tas2557-ioctl-abi.json`：ARM64 为 `0xf53d3701..08`，ARM32 为 `0xf5353701..08`。补丁只在锁定源码的专用构建目录临时应用，退出后反向移除；补丁 SHA256 写入构建溯源。

### 分区检查与文件系统识别

`inspect_package.py` 读取 rawprogram XML、验证 6 个 GPT 模板的头/分区表 CRC、解析实际 GPT 容量，并按 Android sparse 头计算**展开后的尺寸**。不以压缩包或稀疏文件占用磁盘的尺寸决定能否写入。

实际发现 `mi_product.img` 展开 2 MiB，而包内 XML 与 GPT 均仅留 256 KiB；`mi_ext` 也必须核对。EDL GPT 模板的末尾占位项可能需要 patch XML 按实际介质容量修补，所以模板不能当实机 GPT。用户还使用刷机匣通用 845 引导，进一步要求从实机读回核对。

已解出的国行 donor system/system_ext/product 是 EROFS（4 KiB block，LZ4 padding），旧包 boot ramdisk 与 vendor fstab 将这些分区声明为 ext4。因此即使尺寸够大，直接替换镜像也无法正确挂载。未来需同步适配 first-stage ramdisk 和 vendor fstab，或选择可验证的重打包格式；此处尚未生成或刷入新的 boot/ROM。

### 崩溃诊断的已写实现

ADB 收集器只读、有超时和日志条数上限，保留权限不足错误，默认不收 IMEI、不上传。开启 `--include-logs` 可收 crash/radio、pstore、dmesg、DropBox 索引，输出仅存本地 private 目录。

已核对 donor 自带 `logcatlog` 服务和 SELinux 标签，写出待集成的日志 overlay：复用 `kernellog` 域、`offlinelog_file` 路径，将原 640–1280 MiB 的全量离线日志配置替换为仅 crash buffer、约 5 MiB 环形文件；由开关控制启动，不采集常驻 radio，不启用全局 debug trace。文件见 `device/polaris/diagnostics/`。**尚未打入 ROM，SELinux enforcing 与待机功耗尚未真机验证。**

## 已调查但尚未解决的兼容层

本次目标固定为中国版 HyperOS 3 / **Android 15**；Android 17 旧包仅为参考。新增 `audit_sepolicy.py` 发现 system/system_ext/product 三处均缺少 vendor 要求的 `202504.cil`，旧 precompiled policy 的三组来源 hash 均不匹配，报告为阻断，未用 permissive 或伪造版本绕过。候选 OrangeFox 的主/备用分区配置、自动切换逻辑、文件系统支持和解密需一起适配，详见 [recovery.md](recovery.md)。

| 层 | 现有证据 | 下一步验证/实现 |
|---|---|---|
| CPU/用户空间 | donor 保留 arm64 与 arm32 ABI，页大小为 4 KiB | 检查 APEX/bionic/native ELF 的指令基线、linker namespace，禁止仅修改 ABI 属性 |
| VINTF | vendor FCM 6；donor FCM 6 包含 4.19.191 条目；名称清单未发现缺失的必需 provider | 跑完整 checkvintf，核对版本/instance/transport/conditional kernel configs 与服务实际注册 |
| SELinux | 旧 vendor `plat_sepolicy_vers.txt=202504`，donor 未提供 202504 映射 | 移植/重建与 Android 15 平台匹配的 vendor policy，解决具体符号与规则；不得改版本数字充当适配 |
| RIL/IMEI | 旧 vendor 有 qcrild 双实例、rmt_storage、radio HAL | 保留 polaris modem/EFS/校准，核对权限/节点/动态库，实测双卡注册、原 IMEI、通话/数据/IMS |
| Wi-Fi/蓝牙 | 指定内核内建 QCA_CLD_WLAN，旧 vendor 为 SDM845 配套固件/服务 | 核对 firmware request 名称与路径、persist 校准、驱动控制接口，实测睡眠/唤醒与共存 |
| 温控/功耗 | 内核已有 TSENS，旧 vendor 有 thermal-engine 与低功耗 init | 核对实际 sysfs 写入、thermal 接管、suspend residency；测待机/负载/充电，不以玄学属性替代 |
| 小米云/账号 | 国行 donor 存在云备份、查找设备、账号相关权限/组件 | 保留原签名及依赖，实测登录/同步/推送；不伪造证书、IMEI或绕过账号锁 |
| 启动/存储 | 静态物理分区；logdump 被作 metadata；刷机匣通用引导 | 读取真实 GPT、fstab、加密状态、boot header；确认回退后才构造安装器 |

## 将来移植 HyperOS 4 的顺序

1. 先复制工程结构和验收方法，创建新的 dev 工作版本；重新锁定 **China** donor 与实际 Android API。版本名称、设置页、uname 字符串均可伪装，不能作为唯一依据。
2. 保留 polaris 的 modem/校准、硬件 HAL、设备树和合适的内核基线。只从 donor 取经审计的 framework/APEX/系统应用；新 SoC 的 boot/vendor/DTB/thermal/Power HAL 不直接混入。
3. 先做差异清单：CPU/页大小、APEX/native ELF、HAL/VINTF、SEPolicy 版本、BPF 特性、Binder/cgroup/ION/DMA-BUF、分区容量/文件系统、FBE/Keymaster。逐项给出“来源证据→具体修改→自动检查→真机用例→回退”。
4. 新 Android 需要的 BPF 能力用 program/map/helper/verifier 实测确认，先看指定内核已有 backport；避免同一功能重复移植。不对未知功能谎报支持。
5. 先打通第一阶段挂载、SELinux enforcing、桌面与存储，再处理 RIL、Wi-Fi、图形/音频/相机。每次只改一个可归因的依赖集合，记录构建 SHA 与日志。
6. 硬件可用后再优化：基线温度/电流/深睡/唤醒次数/服务重启次数对比；保留电池保护和热关机。NFC 可以延后，基带、数据丢失、温控失效不能延后。
7. 崩溃日志默认本地、限量；公开 issue 只贴脱敏片段和构建编号。IMEI、QCN/EFS、Wi-Fi 密钥、账号 token、原始 bugreport 不进公开仓库。
8. 将测试证据与具体镜像哈希绑定；通过 `release-gates.json` 中全部必要项目后才推进 stable。当前工程的静态检查通过，不代表将来的新 donor 自动兼容。
