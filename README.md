# HyperOS 3 for Xiaomi MIX 2S / polaris

维护者：[@xiziya](https://github.com/xiziya)。目标设备：骁龙 845、6 GB / 128 GB。目标系统：**中国版 HyperOS 3 / Android 15**。

**当前阶段：首次开发测试 ZIP 已生成，六份镜像均通过 ZIP 解压哈希回读。尚未进行真机启动或硬件验收，没有稳定版。** 安装边界和首次测试见 [首次上机说明](docs/first-device-test.md)，完整校验记录见 [封装报告](reports/development-package.json)。封装完成不等于运行成功。

本地产物：`HyperOS3-Polaris-A15-China-dev-20260925.zip`，5,596,345,065 字节；SHA256：`5f7775157bcc22909b466d3cfdfb003f05ba6ea89141584c11d5eb6797c8c1c4`。仓库不托管厂商镜像；此报告用于核对机主本地测试包。

- `dev`：日常开发，工具、来源锁定、兼容性调查。
- 旧 unofficial 橙狐的安装器识别修订及剩余 Data 阻断见 [r3 修订说明](docs/installer-revision-r3.md)；r3 完整包哈希单独记录于 `reports/development-package-r3.json`，六个镜像与首包一致。
- `stable`：稳定发布入口。只有完成设备验收的版本才可发布；初始分支仅包含项目说明。
- 公开仓库只有所有者具有写权限；其他人可以读取、fork、提交建议，不能直接修改本仓库。

指定内核：`xiziya/114514_kernel_xiaomi_sdm845`，`lineage-23.2_xiaomi`，固定提交 `1f326a9202472e8228c2a08ebfd4fdb83da52675`。

适配目标包括双卡/基带/IMEI读取、Wi-Fi、数据网络、功耗与温控、小米账号和云服务。它们均须实际测试，代码检查不代表硬件通过。不会改写 IMEI、使用他机校准数据或把未测试 ROM 标为稳定。

开发记录见 [bringup](docs/bringup.md)，已实现的修改与未来 OS4 迁移方法见 [兼容性记录](docs/compatibility-and-future-ports.md)，旧包橙狐的调查见 [recovery](docs/recovery.md)。来源见 `config/sources.json`；本地镜像、设备日志和 EFS 备份禁止提交。仓库只分发自写工具和许可允许的源代码，厂商二进制保持本地。

**后续继续移植或换到 OS4 时，先读 [移植交接入口](docs/porting-handoff.md) 和 [兼容实现总结](docs/compatibility-and-future-ports.md)。** 仓库根目录 `AGENTS.md` 也指向这些入口，便于后续会话读取并续接。新增适配按 [记录模板](docs/porting-record-template.md) 留下可验证证据。

ROM 本体适配见 [显示/Wi-Fi 等硬件节点](docs/hardware-nodes.md)；已真实编译的 Android 15 [Lights HAL 候选](docs/lights-hal.md)已装入 Android 15 vendor 工程候选，仍需运行验证；见 [镜像装配记录](docs/integration.md)。
