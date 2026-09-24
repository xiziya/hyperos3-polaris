# 有界自动崩溃日志（待集成）

已核对 ziyi donor 中的 `/system/etc/init/init.offline.log.rc`：已有 `logcatlog` 服务，以 system 身份、`kernellog` SELinux 域启动 `/system/bin/logcatlog.sh`。原脚本记录 main/system/crash/events，最多保留 64–128 个 10 MiB 文件，开发时不直接启用。

此目录提供原脚本的最小替代：仅 crash buffer，1 MiB ×（当前文件 + 4 个轮换文件），umask 077，文件路径保持原样。init 在开机完成后按 `persist.sys.polaris.diag=1` 启动，设为 0 停止。不会打开 radio 日志、网络上报、shell/root 后门，也不修改温控。

这是**待集成的 overlay**，当前没有 ROM 构建器安装它。集成时按原文件 uid/gid、mode 和 SELinux 标签写入，核实 `kernellog` 域读 crash buffer、写原路径权限；稳定版默认不设置开关。不得用 permissive 或放宽全局策略代替正确权限。

验证：制造一个测试应用 Java/native 崩溃，检查 logcatlog 服务、轮换上限、重启后开关行为、SELinux AVC、灭屏功耗；启动完成前的死循环仍需通过 ADB/recovery、DropBox、tombstones 或 pstore 取证，不宣称此服务覆盖所有早期失败。
