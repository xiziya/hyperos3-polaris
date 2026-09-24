# 2026-09-25 实际装配配方

这里记录真实运行过的分阶段配方，方便未来移植复核，不伪称从零一键构建器。先读 `../../docs/development-integration.md` 和来源锁。它们只操作**本机普通镜像文件或本机隔离工作盘**，不用于手机 block device。

设置 `POLARIS_WORKSPACE` 为本机工作目录，其结构为 `outputs/hyperos3-polaris`（本仓库）、`work/research`（本地来源与提取文件）。配方保留本次 `/var/tmp/polaris-*`、`/mnt/polaris-rom-assembly` 以及 `/mnt/e/CodexWork/hyperos3-polaris/assembled` 等 staging 路径，换环境时需要按实际路径适配。这些是受审计输入路径，不应把整个文件系统当作工作目录。

顺序与输入：

1. 按 `config/sources.json`、`a15-vendor-sources.json` 和 `integration-sources.json` 准备原镜像、纯净 kernel/Lights；先执行主 `tools/` 中 policy、A15 vendor、VINTF normalizer 工具，得到 vendor2。
2. `audit_reference_media_mix.py` 从参考 vendor 的 lib/lib64/bin 提取结果选择 coherent display/C2 组件，做两架构候选依赖检查。`integrate_reference_media.py` 对来源 hash 锁定的 vendor2 副本装入这些组件，输出 vendor3；保留失败副本时会从原 vendor2 重新复制，不会累积修改。
3. 把四份 donor EROFS 用 `fsck.erofs --extract=目录 --xattrs --preserve` 在**本地 ext4 等支持 Linux metadata 的文件系统**完整提取。`prepare_system_images.py` 修改这些树，`build_hardware_overlay.py` 后接 `build_settings_overlay.py` 构建/安装两份 RRO。需要 aapt2、apksigner、keytool；签名私钥只在 `private/overlay-signing`，不上传。
4. `finalize_vendor_boot.py` 从 vendor3 输出最终 vendor、boot 和一致 fstab。`run_vintf_core.py` 以最终 vendor 检查两向兼容；`check_media_dlopen.py` 是保守静态导出检查。
5. 主工具 `tools/repack_erofs.py` 对四个树分别重建、fsck、只读 mount、逐文件 metadata/hash 比对。`tools/package_development_rom.py` 根据最终报告与实机布局生成 recovery ZIP，再从 ZIP 解压所有镜像核对 SHA。

本次成功配方是有阶段顺序和前置输入的 one-shot 操作，有些会拒绝已有完成目录/已修改树，不能不看输入就重复运行。来源 hash 不符应重新审计；不要为了跳过检查直接替换期望 hash。旧原始二进制、完整反编译内容、设备日志、EFS 和密钥均不属于本仓库。

静态检查的范围与盲区见对应报告，尤其不能把平面 ELF 清单替代真实 linker namespace，不把 VINTF core 结果替代注册/功能测试，不把现有第三方 ROM 节点读数当作新 ROM 已通过。
