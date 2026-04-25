#!/bin/bash
#
# 2026-04-25, Created by H Fuchs <code@hfuchs.net>
#
# GPU local check for CheckMK
#
# TODO
# Name of the Card.  How?
# # lspci -s $(basename $(readlink -f /sys/class/drm/card0/device))
# c3:00.0 Display controller: Advanced Micro Devices, Inc. [AMD/ATI] Strix Halo [Radeon Graphics / Radeon 8050S Graphics / Radeon 8060S Graphics] (rev c1)
#
# Generalise to more than one.
#

# Thresholds
warn=80
crit=95

gpu_busy=$(cat /sys/class/drm/card0/device/gpu_busy_percent 2>/dev/null || echo 0)
vram_total=$(cat /sys/class/drm/card0/device/mem_info_vram_total 2>/dev/null || echo 0)
vram_used=$(cat /sys/class/drm/card0/device/mem_info_vram_used 2>/dev/null || echo 0)

if [ "$vram_total" -gt 0 ] 2>/dev/null; then
    vram_pct=$((vram_used * 100 / vram_total))
else
    vram_pct=0
fi

echo "P 'GPU Usage' VRAM%=${vram_pct};${warn};${crit};0;100:GPU%=${gpu_busy};${warn};${crit};0;100 'GPU0 is at ${gpu_busy}% GPU, ${vram_pct}% VRAM usage.'"
