# 首启 init 属性重复导致回退：r4 Vendor 修复

用户刷入 r3 后看到 MI 标志并回到 recovery。六个分区实机哈希与构建报告一致。新 recovery 已由用户安装并能启动、挂载 EROFS、提供 ADB/pstore；电量 UI 显示感叹号，单独待修，不能等同于系统充电能力验收。

新 recovery 保留的系统启动 pstore 显示：指定 4.19 内核已启动，system/vendor/system_ext/product 均挂载成功；split SELinux CIL 已编译并加载；第二阶段 init 在属性序列化时报 `Duplicate prefix match detected for 'persist.radio.imei'`、`Failed to initialize property area`，随后 InitFatalReboot。该启动日志最终请求 `bootloader`，机主观察到回到 recovery。不要把旧 recovery 无 EROFS 导致的“system empty”当作这次 init 崩溃的原因。

审计五份 property_contexts，发现五个相同 prefix：persist.radio.imei、persist.radio.meid、ro.ril.oem.imei、ro.ril.oem.meid、ro.ril.miui.imei。每个都在 donor system_ext 和 polaris vendor 定义，标签不同。`tools/fix_deviceid_property_contexts.py` 严格核对这五个来源/标签后，保留 donor 的 deviceid_prop / miui_deviceid_prop，去掉 vendor 重复声明；为 vendor 原本有权读取/设置 vendor_deviceid_prop 的 rild 域添加对这两个 donor 标签的同等读/设置权限。其余厂商属性、原有权限和 donor app 权限保留。不伪造或写入任何设备标识。

仅修改 Vendor 中的 vendor_property_contexts、vendor_sepolicy.cil。两文件写后回读内容、uid/gid/mode 和 SELinux xattr；整体 e2fsck 通过。与 donor 三组 policy/mapping 重新执行 secilc，neverallow 检查保留，没有 permissive 或 -N。五份属性规则没有重复 exact/prefix 键；23 项单元测试通过。输入/输出镜像哈希见 `reports/vendor-property-fix-r4.json`。这修复了已定位的最早 fatal，不保证后续首启或硬件已通过。

本地修复镜像为 vendor-polaris-a15-r4-property-fix.img，仅供当前 r3 镜像组合使用，必须写 Vendor（或 recovery 显示的 Vendor Image），不能写 Boot/System/Recovery。无需格式化 Data。助手只传输文件并校验，未自动刷写或重启。下一次系统启动失败后保留新 recovery 的 pstore，继续按最早 fatal 排查。

机主追加要求备份双卡 IMEI，已只读保存本机 modemst1/modemst2/fsg/fsc/persist，各分区电脑 SHA 与设备前后两次读数一致；旧备份保持不变。Recovery 未提供可读 IMEI1/2 明文，底层备份不等于号码读取或恢复已验证。完整镜像、哈希、属性查询和原始日志只保存在忽略的 private 目录，不上传。
