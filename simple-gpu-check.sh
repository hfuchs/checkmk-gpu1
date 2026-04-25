#!/bin/bash
#
# 2026-04-25, Created by H Fuchs <code@hfuchs.net>
#
# GPU local check for CheckMK
#

# Read values from sysfs (integers in KB)
gpu_busy=$(cat /sys/class/drm/card0/device/gpu_busy_percent 2>/dev/null || echo 0)
vram_total=$(cat /sys/class/drm/card0/device/mem_info_vram_total 2>/dev/null || echo 0)
vram_used=$(cat /sys/class/drm/card0/device/mem_info_vram_used 2>/dev/null || echo 0)

# Calculate VRAM usage percentage (integer)
if [ "$vram_total" -gt 0 ] 2>/dev/null; then
    vram_pct=$((vram_used * 100 / vram_total))
else
    vram_pct=0
fi

# Thresholds: 80% warn, 95% crit
warn=80
crit=95

echo "P 'GPU Usage' VRAM%=${vram_pct};${warn};${crit}:GPU%=${gpu_busy};${warn};${crit} 'GPU0 is at ${gpu_busy}% GPU, ${vram_pct}% VRAM usage.'"


