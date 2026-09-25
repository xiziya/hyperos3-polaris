# MIX 2S 6/128 首次开发包测试

目标：中国版 HyperOS 3 / Android 15，真实 4.19.325 纯净内核。此包只适用于已只读采集的 **polaris 静态分区布局**，没有完成首启或硬件验收，不是 stable。不含 KSU/SukiSU，也未开启内核版本伪装。

## 当前 recovery 实测阻断（r2）

机主 unofficial OrangeFox 的 TWRP/Fox 版本属性为空。首包错误提示 `Run only in TWRP/OrangeFox recovery` 发生在任何分区写入之前。r2 改为核验 init 的 recovery 服务、实际 recovery 进程路径及 `/etc/recovery.fstab`，并提供显式 `--preflight-only` 模式；通过检测不代表解密能力已通过。

实机只读预检已通过 recovery、机型、工具、ZIP manifest、userdata 布局/挂载/旧数据检查，但发现格式化后的 ext4 缺少 `encrypt` 特性。旧 recovery 的 mke2fs 配置不默认启用该特性。**不要因此反复 Format Data，也不要删掉加密检查继续刷。** 需要先另行确认可用的格式化或离线文件系统特性修复方案；r2 不自动修改 userdata，不会绕过此阻断。

## 安装路线

沿用现有分区，不需要为了容量重新 9008 分区，不使用刷机匣的通用 rawprogram/flash_all。包仅包含 system、system_ext、product、mi_ext、vendor、boot；boot 最后写入。不写 GPT、引导链、recovery、vbmeta、modem、EFS、persist、userdata。

1. 先把手机个人文件、账号恢复方式和现有系统的必要备份保存到电脑。已有本地 EFS/boot 备份不包括照片/应用数据，也不代表已经测试过回退。
2. 确认当前 recovery 能进入、触摸/USB/ADB 可用。旧 unofficial OrangeFox 的自动切分区、格式化辅助菜单不属于本项目安装流程，不运行这些工具。新 OrangeFox 只有构建成功后才会另给镜像，解密仍需实测。
3. Android 17 降级到 Android 15 首次安装按清刷处理。**在 recovery 中明确执行 Format Data 会清空内部存储，包括照片和下载文件，必须先完成备份。** 需要 ext4 并带 encryption 文件系统特性。不能用“保留旧数据”碰运气，也不能仅删除锁屏文件。
4. 格式化后通过 USB 重新传入 ZIP，核对同目录 SHA256。保持 /data 挂载，取消 System/Vendor/Product/System Ext 等目标分区的挂载；在 recovery 中手动选择 ZIP 安装。它是本地开发 ZIP，没有厂商 OTA 签名。
5. 安装器先检查机型、全部 by-name 映射、容量/起点、挂载和 device-mapper holders、/data 清理状态、所有镜像长度和 SHA256，然后才写入。每个分区写后再次读回 SHA256。发现任何不匹配会退出；保存界面错误和 recovery.log，不修改安装器绕过检查。
6. 成功后手动重启。没有自动重启或自动清数据。如果中途写入失败，保持 recovery，不启动半套镜像。不要将旧 OS4 的部分 system/vendor 与新 boot 随意混刷。

旧 recovery 是否能完成本包的 ZIP64 读取、ext4 encryption 格式化，以及新 ROM 首启后的 FBEv2 解密，仍是待验证项。安装器对格式和布局的检查不能代替 recovery 解密或回退实测。首次测试前应确保旧完整包、备份和原来可用的救援方式仍在电脑上；本工程不自动运行 9008 救援。

## 首次启动观察与日志

首次主要看桌面、触摸/亮度、双卡与原 IMEI、4G 数据、Wi-Fi、充电温度和存储。先短时间观察，出现明显异常升温、连续重启或充电异常就停止测试。NFC 可后测；视频解码、录制、相机、后置指纹、小米账号/云服务分别记录结果，不能用“进桌面”代替验收。

“设置 → 我的设备”应对应 MIX 2S、SDM845/骁龙 845；RAM 与存储由系统真实统计，市场规格为 6GB/128GB，可用容量更少是正常的。5G 蜂窝、屏下指纹、AOD、120Hz、挖孔屏和 Wi-Fi 6 专属配置已做清理；5GHz Wi-Fi、后置指纹、双卡 4G、NFC 等属于支持但需验收的功能。

崩溃日志默认限量写入 `/data/local/log/logcatlog.txt*`，约 5MiB；系统自身 tombstone 上限 10 份，内核启用 pstore。默认不常驻记录 radio 全量日志，不上传日志。通过已有 `tools/collect_device.py` 只读采集；不要求为诊断刷入 Root。公开问题只贴脱敏内容，不上传 IMEI、序列号、EFS/QCN、账号 token 或完整私有日志。

稳定验收项目仍见 `config/release-gates.json`。首次开发包的存在不会自动将任何真机项目标记为通过。
