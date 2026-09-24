# Android 15 Lights HAL 候选

目标是替换用户提供的 OS4 包中最低要求 SDK36 的 lights APEX。当前已从 Android 15 对应源码构建 **arm64 / API35 / AIDL ILights V2** 可执行文件，尚未集成到 vendor 镜像或真机验证。

## 实现方式

使用 LineageOS `android_hardware_lineage_interfaces` 的 `lineage-22.2` 灯光实现（固定 SHA）。它枚举 `panel0-backlight`，读取 `max_brightness`，将 Android RGB 亮度转换为节点范围。指定内核的 polaris JDI/EBBG DTS 最大值为 4095。源码没有引入 donor 的面板、HBM、刷新率或 SoC 功耗参数。

AIDL compiler、平台 Binder 头、libbase 与 light V2 API 全部来自固定 Android 15 来源。使用官方 NDK r27c，目标 API35；静态链接 NDK libc++ 和必要 libbase 源码，生成的 AIDL 代码编进服务，避免跨 vendor/platform 使用 C++ 私有 ABI。保留 `BINDER_STABILITY_SUPPORT` 与 vendor 编译身份，不能省略 VINTF 稳定性标记。

链接时使用目标国行 donor 的 `libbinder_ndk.so`，因为普通 NDK stub 不包括服务注册和 VINTF 稳定性所需的平台扩展。这仅是链接输入，不复制 donor libc/binder 库到 vendor。直接动态依赖为 `libbinder_ndk.so`、`liblog.so`、`libm.so`、`libdl.so`、`libc.so`。仍需在最终 linker namespace 中运行检查。

## 可重复构建

在 Linux x86_64、Python 3.12+ 和 host `c++` 环境使用 `tools/build_lights_hal.py`。`config/lights-build-sources.json` 锁定每个归档、工具、链接输入及源码文件 SHA256；源地址中的 Gitiles `?format=TEXT` 下载后必须 Base64 解码。

准备一个仅存本地的 JSON 路径映射：

```json
{
  "ndk_archive": "/cache/android-ndk-r27c-linux.zip",
  "toolchain": "/cache/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64",
  "libbase_archive": "/cache/libbase-a15.tar.gz",
  "binder_headers_archive": "/cache/binder-platform-a15.tar.gz",
  "llndk_header": "/cache/llndk-versioning.h",
  "aidl": "/cache/aidl",
  "aidl_libcxx": "/cache/libc++.so",
  "binder_library": "/extracted-donor/system/lib64/libbinder_ndk.so",
  "light": "/sources/android_hardware_lineage_interfaces/light",
  "light_api": "/sources/android_hardware_interfaces/light/aidl/aidl_api/android.hardware.light/2"
}
```

源码目录使用锁定提交和 Git 原始字节（关闭 CRLF 自动转换）。`light_api` 的 `.hash` 取最后一行作为 V2 frozen hash。NDK 解压必须保留 Unix symlink；脚本逐文件核对解压后的 LLVM 工具链与已校验的官方 ZIP，拒绝漂移。不要使用容量不足的 tmpfs 存放 NDK。

```sh
python3 tools/build_lights_hal.py --inputs /private/lights-inputs.json --output /var/tmp/polaris-lights-new
```

输出包含可执行文件、完整构建命令、源码锁摘要、ELF 明细、许可证与构建目录。构建脚本从锁定文件清单复制源文件，额外的 `.cpp` 不会进入构建。归档仅提取普通文件/目录，不跟随 libbase 指向外部 Soong 的 `.clang-format` 链接。厂商链接输入与本地产物不要提交公开源码仓库。

## 检查边界

- 主机测试编译真实上游 `Utils.cpp`，遍历最大值 255 和 4095 下的 512 个亮度输入，检查范围、单调性、端点与灰阶换算。
- `reports/lights-elf-audit.json` 记录候选 ELF 与 donor 库清单比对。候选依赖闭包中未发现缺失库名和强符号；主程序 109 个带版本的强符号需求均在指定候选库中找到匹配。未逐一验证依赖库的版本符号，不包含完整 linker namespace、dlopen、CPU 指令基线或运行时验证。
- 背光数值测试不覆盖亮度曲线、低亮闪烁、屏幕开关、自动亮度、通知灯模式和 SELinux enforcing。
- 上游实现的设备发现发生在服务启动阶段，sysfs I/O 失败传播并不完善。应通过服务 dump、AVC 与实际节点读回验证，不能单凭 Binder 调用返回成功判断亮度已经写入。

集成文件与必要条件见 [device/polaris/lights](../device/polaris/lights/README.md)。完成候选服务不代表其余 SDK36 APEX、Wi-Fi/Keystore Binder ABI 和旧 vendor SEPolicy 已解决。
