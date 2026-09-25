# 旧 unofficial OrangeFox 的安装器兼容修订

机主请求暂不等待自编译 recovery CI，先修复原开发包对现有橙狐的误判。原安装器仅查 `ro.twrp.version` / `ro.orangefox.version`，而实机两项为空。当前安装器核验 recovery 服务、进程真实路径及 fstab；不再要求品牌版本属性。机型、实际分区映射/容量/起点、挂载、Data 状态以及全部镜像哈希检查继续保留。

`r3` 使用原完整包的六个镜像，只替换安装器、封装元数据和首次测试说明。`tools/revise_development_installer.py` 校验原包 SHA256、用 Info-ZIP 在独立输出盘创建新包，再解压每个镜像核对大小和 SHA256，拒绝重复 ZIP 条目。原包不覆盖。`r2` 曾尝试封装但因磁盘 I/O 失败，未产出可交付包。

实机只读预检已通过 recovery 识别，并在 Data ext4 缺少 `encrypt` 特性时按预期停止，没有写入 ROM 分区。Data 只有 lost+found/media，未发现检查范围内的旧 Android 数据/密钥目录。改变识别条件并不能修复缺失的文件系统能力。

旧橙狐自带 `unzip` 在实机完整读取了原包的 `images/product.img`（4,493,500,416 字节），SHA256 为 `b4097c742a826963fbabc6fc5da376923751079524757be0498bb42b25d472f9`，与已验证镜像一致。此结果证明该大 ZIP 条目的解压读取通过，不代替所有镜像预检、安装写入或解密验收。

可选的 `tools/enable_data_encrypt_feature.sh` 独立于安装器，必须由机主另行明确同意才用于真实 userdata。它要求 recovery、polaris、精确 userdata 映射/大小/起点、Data 和内部存储已卸载且没有 mapper holder；先执行只读 fsck，成功后仅 `tune2fs -O encrypt`，再只读 fsck 和特性回读。不执行格式化、自动修复、ROM 刷写或重启。当前仅在 recovery `/tmp` 的 RAM 临时镜像上验证过相关工具，真实 userdata 未修改。这不是 FBEv2/Keymaster 或 recovery 解密已验证的结论。

首启和硬件验收仍未完成；稳定发布门槛保持未通过。

## 后续实机处理：已获明确授权并完成

补齐后，r3 安装器源码的 `--preflight-only` 已在当前旧橙狐完成全部检查并返回 0：目标分区映射/容量/起点/挂载状态和六个解压镜像的长度、SHA256 全部通过。读取的是手机原包（其六个镜像与 r3 相同），没有执行安装写入阶段；手机上原 ZIP 内嵌安装器仍旧，正式测试须使用完整 r3 包。

机主随后明确要求在旧 recovery 中补齐特性。执行 `twrp unmount /data` 后确认 userdata 在 `/data` 和 `/sdcard` 的挂载均已解除；维护脚本检查实际分区和只读 fsck，通过后执行 `tune2fs -O encrypt`，再执行只读 fsck，均成功。私有 superblock 回读显示 incompat 从 `0x42` 变为 `0x10042`，增加 encrypt 位。重新挂载 Data/内部存储后可见原 ROM ZIP。见 `reports/data-encrypt-feature.json`。没有格式化、刷写 ROM 或重启；这不等于首启后的 FBEv2/Keymaster/解密已验收。旧 recovery 再次 Format Data 可能重新丢失该特性，因此不要重复格式化。
