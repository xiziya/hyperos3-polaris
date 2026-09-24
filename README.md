# HyperOS 3 for Xiaomi MIX 2S / polaris

维护者：[@xiziya](https://github.com/xiziya)。目标设备：骁龙 845、6 GB / 128 GB。目标系统：**中国版 HyperOS 3 / Android 15**。

**当前阶段：离线调查与适配开发。尚无可刷 ROM；没有通过真机验证的稳定版。**

- `dev`：日常开发，工具、来源锁定、兼容性调查。
- `stable`：稳定发布入口。只有完成设备验收的版本才可发布；初始分支仅包含项目说明。
- 公开仓库只有所有者具有写权限；其他人可以读取、fork、提交建议，不能直接修改本仓库。

指定内核：`xiziya/114514_kernel_xiaomi_sdm845`，`lineage-23.2_xiaomi`，固定提交 `1f326a9202472e8228c2a08ebfd4fdb83da52675`。

适配目标包括双卡/基带/IMEI读取、Wi-Fi、数据网络、功耗与温控、小米账号和云服务。它们均须实际测试，代码检查不代表硬件通过。不会改写 IMEI、使用他机校准数据或把未测试 ROM 标为稳定。

开发记录见 [bringup](docs/bringup.md)，已实现的修改与未来 OS4 迁移方法见 [兼容性记录](docs/compatibility-and-future-ports.md)，旧包橙狐的调查见 [recovery](docs/recovery.md)。来源见 `config/sources.json`；本地镜像、设备日志和 EFS 备份禁止提交。仓库只分发自写工具和许可允许的源代码，厂商二进制保持本地。
