# SPDX-License-Identifier: GPL-3.0-or-later
# Derived from OrangeFox polaris/sdm845-common (2019-2026 OrangeFox Project).
PRODUCT_RELEASE_NAME := polaris
DEVICE_PATH := device/xiaomi/polaris
SDM845_COMMON_PATH := device/xiaomi/sdm845-common
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/full_base_telephony.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/languages_full.mk)
$(call inherit-product, vendor/twrp/config/common.mk)
PRODUCT_DEVICE := polaris
PRODUCT_NAME := twrp_polaris
PRODUCT_BRAND := Xiaomi
PRODUCT_MANUFACTURER := Xiaomi
PRODUCT_MODEL := Mi MIX 2S
PRODUCT_SHIPPING_API_LEVEL := 27
PRODUCT_SOONG_NAMESPACES += $(DEVICE_PATH) $(SDM845_COMMON_PATH) vendor/qcom/opensource/commonsys-intf/display
PRODUCT_PACKAGES += qcom_decrypt qcom_decrypt_fbe android.hardware.keymaster@3.0.vendor android.system.keystore2 android.hardware.usb@1.0-service
TARGET_RECOVERY_DEVICE_MODULES += libion vendor.display.config@1.0 vendor.display.config@2.0 libdisplayconfig.qti
RECOVERY_LIBRARY_SOURCE_FILES += $(TARGET_OUT_SHARED_LIBRARIES)/libion.so $(TARGET_OUT_SYSTEM_EXT_SHARED_LIBRARIES)/vendor.display.config@1.0.so $(TARGET_OUT_SYSTEM_EXT_SHARED_LIBRARIES)/vendor.display.config@2.0.so $(TARGET_OUT_SYSTEM_EXT_SHARED_LIBRARIES)/libdisplayconfig.qti.so
PRODUCT_PROPERTY_OVERRIDES += ro.orangefox.dynamic.build=false ro.fox.keymaster_version=3
PRODUCT_VENDOR_PROPERTIES += vendor.usb.use_ffs_mtp=1 sys.usb.mtp.batchcancel=1

# Staging copies only pinned hardware libraries/HAL executables and the 4.19 USB rc.
# It excludes upstream dynamic switching, repartitioning and format helper scripts.
PRODUCT_COPY_FILES += $(call find-copy-subdir-files,*,$(DEVICE_PATH)/recovery/root/,$(TARGET_COPY_OUT_RECOVERY)/root/)
