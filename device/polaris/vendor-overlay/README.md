# ROM 硬件节点 overlay（待集成）

这里适配的是 HyperOS 3 / Android 15 ROM，不是 recovery。

`init.polaris.nodes.rc` 在 post-fs-data 阶段为已存在的 `/sys/module/wlan/parameters/fwpath` 设置 wifi:wifi、0660。依据：指定内核以 0644 注册该参数；原 `libwifi-hal.so` 使用此路径，HAL rc 以 wifi 身份运行；旧 vendor init/ueventd 未找到该路径的授权。donor 平台策略已有准确 genfscon 标签和 hal_wifi 写权限，因此不增加宽泛 SELinux allow，也不改成 0666。是否在实机还由其他代码调整过权限，需要启动日志与实际 stat 确认。

`tools/prepare_vendor_overlay.py` 另对锁定的旧 post-boot 脚本生成修改副本，移除 IRQ 7/493 的绑核写入，保留内核默认亲和性与 `vendor.post_boot.parsed=1`。不把旧内核的 IRQ 编号带进新内核，也不把 perf 初始化完成信号误删。

输出是待重打包的文件，不是已刷入的修改。SELinux 策略、vendor APEX SDK、HAL 依赖与实机布局阻断尚未解除。集成需保持 init rc 原有路径标签及文件权限，检查 init 导入、AVC、Wi-Fi STA/热点、显示/触摸、深睡和充电。
