#!/bin/bash
#
# 2026-04-25, Created by H Fuchs <code@hfuchs.net>
#
# TODO Implement the obvious calculations.
#

gpu_busy=...    # via /sys/class/drm/card0/device/gpu_busy_percent
vram_total=...  # via /sys/class/drm/card0/device/mem_info_vram_total
vram_used=...   # via /sys/class/drm/card0/device/mem_info_vram_used

echo "P 'GPU Usage' VRAM%=value;warn;crit:GPU%=value;warn;crit 'GPU0 is at value% GPU, value% VRAM usage.'"


