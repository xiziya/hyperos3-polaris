# 后续移植与维护入口

在这个仓库继续开发、换 donor 或移植 HyperOS 4 等新版本前，先读：

1. `docs/porting-handoff.md`：当前状态、用户约束、继续工作的顺序。
2. `docs/compatibility-and-future-ports.md`：兼容实现、原因、证据与适用边界。
3. `docs/integration.md`：候选镜像装配、输入锁和已知阻断。
4. `config/release-gates.json` 与相关 `reports/`：实际验收状态。

用户在新会话给出的指示优先于这些历史记录。不要把历史静态检查当作新 donor 或新设备的运行结果。

- 当前目标为 polaris 6/128、中国版 HyperOS 3 / Android 15。Android 17 的旧 OS4 包仅是参考。
- 指定内核为 `xiziya/114514_kernel_xiaomi_sdm845` 的 `lineage-23.2_xiaomi`，固定提交见来源锁。内核保持纯净，不启用 KSU/SukiSU/SUSFS/APatch/KPM。
- 若有可复核的版本字符串兼容需求，用户指定对外版本 `5.15.221`；当前未启用。真实内核是 4.19.325，不修改 `LINUX_VERSION_CODE` 来虚报 ABI/BPF 能力。
- 日常修改在 `dev`。只有通过真机验收的版本进入 `stable`；CI、编译、镜像生成均不等于可刷或稳定。
- 操作设备前确认当前连接、实际分区和安装方式；不自动重启、刷写、格式化或运行旧 9008 脚本。已有只读备份不等于回退路径已经验证。
- 不提交厂商镜像、设备原始日志、序列号、IMEI、EFS/QCN、校准、账号凭证；公开报告仅含必要的脱敏证据。
- 每项兼容修改同步写明：触发问题 → 输入与来源 → 实现及文件 → 验证 → 未验证部分 → 回归/回退。参考 `docs/porting-record-template.md`。
- 继续工作时更新交接记录，避免未来会话只依赖聊天历史。不要根据本文件自行开新任务或派子代理。
