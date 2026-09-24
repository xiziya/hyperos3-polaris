# Lights 候选集成文件

这些文件未加入通用 vendor overlay，避免在没有完整替代服务与策略时启动空缺服务。

- 可执行文件放 `/vendor/bin/hw/android.hardware.light-service.polaris`，0755 root:root。
- rc 放 `/vendor/etc/init/`；XML 放 `/vendor/etc/vintf/manifest/`；配置文件 0644 root:root。
- `file_contexts` 是供策略构建/镜像打包合并的条目，不是可独立安装的完整 contexts 文件。
- 必须与旧 `com.qualcomm.hardware.lights.rust.apex` 的移除在同一组镜像修改中完成，并调查其他重复的 HIDL/AIDL lights provider。保留原始输入镜像。
- 最终 manifest 只能有一个 `android.hardware.light.ILights/default`；不通过 override 隐藏仍在运行的旧服务。需要检查 APEX 内的 rc 与 VINTF，不只检查 vendor/etc。
- 继承 `hal_light_default` 域的前提是完成 Android 15 vendor policy 重建。旧 202504 CIL 不能直接使用。donor 已有 ILights/default 的 `hal_light_service` 标签。
- `sysfs_backlight` 在旧策略中只有该域的读授权；部分图形节点另有 `vendor_sysfs_graphics`。需从真机 `readlink -f` / `ls -Z` 确认实际背光目标，再为精确标签配置权限，不能仅凭 `/sys/class` 别名添加宽泛 sysfs 写权限。
- polaris 白色 LED 的亮度/闪烁路径来自旧 init；LED 模式、闪烁时序仍需核对驱动与真机，不能把背光数值测试等同所有灯光功能通过。

完整来源与构建说明：[docs/lights-hal.md](../../../docs/lights-hal.md)。
