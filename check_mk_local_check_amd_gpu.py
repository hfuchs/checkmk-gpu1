#!/usr/bin/env python3
"""
CheckMK Local Check for AMD GPUs (ROCm)

This script collects AMD GPU metrics via rocm-smi and outputs them in CheckMK format.
Place this file in /usr/lib/check_mk_agent/local/check_amd_gpu for CheckMK automation.

Metrics collected:
- GPU name and index
- Temperature (°C)
- Power consumption (W)
- Memory usage (MiB, percentage)
- Fan speed (%)
- GPU utilization (%)

Example rocm-smi output format:
{
  "result": {
    "data": {
      "gpu_list": [{
        "product_name": "AMD Radeon RX 7900 XTX",
        "gpu_memory_usage": {"utilization_pct": 95, "memory_total": "32GB", "memory_used": "16GB"},
        "core_clock": {
          "temperature": {"hotspot_thermal": {"value": 58.2}}
        }
      }, ...]
    }
  }
}
"""

import json
import os
import subprocess
import sys

SERVICE_NAME = "amd_gpu"


def run_rocm_smi():
    """Execute rocm-smi and parse JSON output"""
    try:
        result = subprocess.run(
            ['rocm-smi', '--showall', '-o', 'json'],
            capture_output=True,
            text=True,
            timeout=30,
            check=False
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
    except subprocess.TimeoutExpired:
        return None
    except FileNotFoundError:
        return None
    except Exception:
        return None


def extract_gpu_info(root_data):
    """Extract list of GPUs from rocm-smi response in various formats"""
    if root_data is None:
        return []

    gpus = []

    # Standard rocm-smi format
    if isinstance(root_data, dict):
        # Try 'gpu_list' at various levels
        for key in ['gpu_list', 'gpu-list', 'GpuList']:
            if key in root_data:
                val = root_data[key]
                if isinstance(val, list):
                    gpus = val
                    break
                elif isinstance(val, dict):
                    gpus = [val]
                    break

        # Try nested data structure
        if not gpus:
            data = root_data.get('data', {})
            for key in ['gpu_list', 'gpu-list', 'GpuList']:
                if key in data:
                    val = data[key]
                    if isinstance(val, list):
                        gpus = val
                        break
                    elif isinstance(val, dict):
                        gpus = [val]
                        break

    if not gpus and len(root_data) > 0:
        # Assume single GPU if root is a non-empty dict
        gpus = [root_data]

    return gpus


def get_temperature(gpu_info):
    """Extract GPU temperature in °C"""
    if not isinstance(gpu_info, dict):
        return 0.0

    # Try common temperature fields
    for key in ['temperature', 'gputemp', 'thermal', 'temp', 'thermal_settings']:
        if key in gpu_info:
            val = gpu_info[key]
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, dict) and 'value' in val:
                try:
                    return float(val['value'])
                except (ValueError, TypeError):
                    pass

    # Nested structure
    core = gpu_info.get('core_clock', {})
    if core:
        thermal = core.get('thermal_settings', core.get('thermal', {}))
        if isinstance(thermal, dict):
            for tkey in ['temperature', 'hotspot_thermal', 'hotspot']:
                if tkey in thermal:
                    val = thermal[tkey]
                    if isinstance(val, dict) and 'value' in val:
                        try:
                            return float(val['value'])
                        except (ValueError, TypeError):
                            pass
                    elif isinstance(val, (int, float)):
                        return float(val)

    return 0.0


def get_power(gpu_info):
    """Extract GPU power consumption in Watts"""
    if not isinstance(gpu_info, dict):
        return 0.0

    for key in ['power', 'power_stats', 'average_power_consumption', '_power']:
        if key in gpu_info:
            val = gpu_info[key]
            if isinstance(val, dict):
                return val.get('value', 0.0) or val.get('average', 0.0)
            if isinstance(val, (int, float)):
                return float(val)

    return 0.0


def get_memory_info(gpu_info):
    """Extract GPU memory information"""
    if not isinstance(gpu_info, dict):
        return {'total': 0, 'used': 0, 'free': 0, 'percent': 0}

    for key in ['memory', 'gpu_memory', 'memory_usage', 'memory_stats', 'vram_usage']:
        if key in gpu_info:
            val = gpu_info[key]
            if isinstance(val, dict):
                return val
            elif isinstance(val, str):
                # Parse string like "16/32768MiB"
                parts = val.split('/')
                if len(parts) == 2:
                    try:
                        return {'used': int(parts[0]), 'total': int(parts[1]), 'free': int(parts[1]) - int(parts[0]), 'percent': int(parts[0]) / int(parts[1]) * 100}
                    except (ValueError, TypeError):
                        pass

    return {'total': 0, 'used': 0, 'free': 0, 'percent': 0}


def get_fan_speed(gpu_info):
    """Extract fan speed in percent"""
    if not isinstance(gpu_info, dict):
        return 0.0

    for key in ['fan_speed', 'fan', 'fan_rpm']:
        if key in gpu_info:
            val = gpu_info[key]
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, dict) and 'value' in val:
                try:
                    return float(val['value'])
                except (ValueError, TypeError):
                    pass

    return 0.0


def get_gpu_load(gpu_info):
    """Extract GPU compute load in percent"""
    if not isinstance(gpu_info, dict):
        return 0.0

    # Try common load fields
    for key in ['gpu_load', 'utilization', 'load', 'compute_load', 'gpuutil']:
        if key in gpu_info:
            val = gpu_info[key]
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, dict) and 'value' in val:
                try:
                    return float(val['value'])
                except (ValueError, TypeError):
                    pass

    return 0.0


def get_gpu_name(gpu_info):
    """Extract GPU model name"""
    if not isinstance(gpu_info, dict):
        return "AMD GPU"

    for key in ['product_name', 'gpu_name', 'name', 'model_name', 'device_name', 'display_name']:
        if key in gpu_info:
            return str(gpu_info[key])

    return "AMD GPU"


def get_gpu_uuid(gpu_info):
    """Extract GPU unique identifier"""
    if not isinstance(gpu_info, dict):
        return None

    for key in ['gpu_uuid', 'uuid', 'device_serial', 'serial']:
        if key in gpu_info:
            return str(gpu_info[key])

    return None


def format_value(value, unit=''):
    """Format a numeric value for display"""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.1f}" + unit
    except (ValueError, TypeError):
        return str(value)


def create_check_output(gpu_info, index):
    """Create CheckMK local check output for a single GPU"""
    gpu_name = get_gpu_name(gpu_info)
    gpu_uuid = get_gpu_uuid(gpu_info) or f"AMD_GPU_{index}"

    temperature = get_temperature(gpu_info)
    power = get_power(gpu_info)
    memory = get_memory_info(gpu_info)
    fan_speed = get_fan_speed(gpu_info)
    load = get_gpu_load(gpu_info)
    memory_pct = memory.get('percent', 0)

    # Build output lists for CheckMK
    items = [
        f"AMD GPU {index}: {gpu_name}"
    ]

    labels = {
        'gpu_name': gpu_name,
        'gpu_index': str(index),
        'gpu_uuid': gpu_uuid
    }

    perfdata = {}

    # Temperature label and perfdata
    if temperature > 0:
        items.append(f"Temperature: {temperature:.1f}°C")
        labels['temperature'] = str(temperature)
        perfdata['temperature'] = {
            'value': temperature,
            'warn': 80,
            'crit': 100,
            'min': 0,
            'max': 0
        }

    # Memory label and perfdata
    if memory.get('total', 0) > 0:
        items.append(f"Memory: {format_value(memory.get('used', 0), ' MiB')}/{format_value(memory.get('total', 0), ' MiB')} ({memory_pct:.0f}%)")
        labels['memory_used'] = format_value(memory.get('used', 0), ' MiB')
        labels['memory_total'] = format_value(memory.get('total', 0), ' MiB')
        perfdata['memory_used'] = {
            'value': memory_pct,
            'warn': 80,
            'crit': 95,
            'min': 0,
            'max': 100
        }

    # Power label and perfdata
    if power > 0:
        items.append(f"Power: {format_value(power, ' W')}")
        labels['power'] = format_value(power, ' W')

    # Fan speed label and perfdata
    if fan_speed > 0:
        items.append(f"Fan: {format_value(fan_speed, '%')}")
        labels['fan_speed'] = str(fan_speed)
        perfdata['fan_speed'] = {
            'value': fan_speed,
            'warn': 50,
            'crit': 100,
            'min': 0,
            'max': 100
        }

    # GPU load label and perfdata
    if load > 0:
        items.append(f"Load: {format_value(load, '%')}")
        labels['load'] = str(load)
        perfdata['gpu_load'] = {
            'value': load,
            'warn': 80,
            'crit': 95,
            'min': 0,
            'max': 100
        }

    return {
        'items': items,
        'labels': labels,
        'perfdata': perfdata,
        'service_name': SERVICE_NAME
    }


def check_amd_gpus():
    """Main function - returns list of CheckMK check outputs"""
    root_data = run_rocm_smi()

    if root_data is None:
        # rocm-smi not available or failed
        return [{
            'items': ['AMD GPU monitoring: rocm-smi not available or failed'],
            'labels': {'status': 'not_found'},
            'perfdata': {},
            'service_name': SERVICE_NAME
        }]

    gpu_list = extract_gpu_info(root_data)

    if not gpu_list:
        return [{
            'items': ['AMD GPU monitoring: no GPUs detected'],
            'labels': {'status': 'no_gpu'},
            'perfdata': {},
            'service_name': SERVICE_NAME
        }]

    checks = []
    for idx, gpu_info in enumerate(gpu_list):
        checks.append(create_check_output(gpu_info, idx))

    return checks


if __name__ == '__main__':
    checks = check_amd_gpus()
    # CheckMK local checks output JSON array
    print(json.dumps(checks, indent=2))
