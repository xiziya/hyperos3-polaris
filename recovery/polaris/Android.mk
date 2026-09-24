# SPDX-License-Identifier: GPL-3.0-or-later
LOCAL_PATH := $(call my-dir)
ifneq ($(filter polaris,$(TARGET_DEVICE)),)
include $(call all-makefiles-under,$(LOCAL_PATH))
endif
