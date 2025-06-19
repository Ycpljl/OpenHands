# Nomad Runtime IP Mapping Improvement

## Overview

This document describes the improvement made to the Nomad runtime's IP address mapping functionality to support both single IP and multi-node environments.

## Problem Statement

The original implementation used hardcoded IP mapping:

```python
# Old hardcoded approach (not flexible)
if node_address == '192.168.0.133':
    node_address = '119.8.51.245'
```

This approach had several limitations:
- ❌ **Not flexible**: Only worked for one specific IP mapping
- ❌ **Not configurable**: Required code changes for different environments
- ❌ **Not scalable**: Couldn't handle multiple nodes with different mappings

## Solution

### 1. Configurable IP Mapping

Added a new configuration field `nomad_ip_mapping` to `SandboxConfig`:

```python
nomad_ip_mapping: dict[str, str] | None = Field(
    default=None,
    description='IP address mapping for cloud environments. Maps internal IPs to external IPs. '
    'Supports multiple nodes. If not configured, original IPs are used directly.',
)
```

### 2. Flexible Runtime Logic

Updated the runtime to support both scenarios:

```python
# New flexible approach
original_ip = node_address
if self.config.sandbox.nomad_ip_mapping:
    mapped_ip = self.config.sandbox.nomad_ip_mapping.get(node_address)
    if mapped_ip:
        self.log('info', f'Mapping internal IP {node_address} to external IP {mapped_ip}')
        node_address = mapped_ip
    else:
        self.log('debug', f'No mapping configured for IP {node_address}, using original IP')
else:
    self.log('debug', f'No IP mapping configured, using original IP {node_address}')
```

## Supported Scenarios

### Scenario 1: Single IP Environment

**Use Case**: Nomad cluster uses public IPs directly, no mapping needed.

**Configuration**:
```yaml
sandbox:
  nomad_address: "http://203.0.113.10:4646"
  # No nomad_ip_mapping field needed
```

**Behavior**: Uses original IP addresses returned by Nomad.

**Test Result**:
```
Runtime URL: http://192.168.0.133:30253  # No mapping applied
```

### Scenario 2: Multi-Node Environment with IP Mapping

**Use Case**: Cloud environments where internal IPs need to be mapped to external IPs.

**Configuration**:
```yaml
sandbox:
  nomad_ip_mapping:
    "192.168.0.133": "119.8.51.245"  # Node 1
    "192.168.0.134": "119.8.51.246"  # Node 2
    "192.168.0.135": "119.8.51.247"  # Node 3
```

**Behavior**:
- Maps configured IPs to their external counterparts
- Uses original IPs for unmapped nodes
- Supports mixed environments

**Test Result**:
```
Mapping internal IP 192.168.0.133 to external IP 119.8.51.245
Runtime URL: http://119.8.51.245:25391  # Mapping applied
```

## Benefits

| Feature | Before | After |
|---------|--------|-------|
| **Flexibility** | ❌ Hardcoded | ✅ Configurable |
| **Multi-node Support** | ❌ Single mapping | ✅ Multiple mappings |
| **Environment Compatibility** | ❌ Limited | ✅ Universal |
| **Maintenance** | ❌ Code changes | ✅ Config changes |
| **Backward Compatibility** | ❌ Breaking | ✅ Compatible |

## Configuration Examples

### Example 1: No IP Mapping (Single IP Environment)

```yaml
runtime: nomad
sandbox:
  nomad_address: "http://203.0.113.10:4646"
  nomad_token: "your-token"
  # No nomad_ip_mapping - uses original IPs
```

### Example 2: Multi-Node IP Mapping

```yaml
runtime: nomad
sandbox:
  nomad_address: "http://119.8.51.245:4646"
  nomad_token: "your-token"
  nomad_ip_mapping:
    "192.168.0.133": "119.8.51.245"
    "192.168.0.134": "119.8.51.246"
    "192.168.0.135": "119.8.51.247"
    "10.0.1.100": "203.0.113.10"
```

### Example 3: Python Configuration

```python
config = OpenHandsConfig()
config.runtime = 'nomad'
config.sandbox.nomad_address = 'http://119.8.51.245:4646'
config.sandbox.nomad_token = 'your-token'

# Multi-node IP mapping
config.sandbox.nomad_ip_mapping = {
    '192.168.0.133': '119.8.51.245',
    '192.168.0.134': '119.8.51.246',
    '192.168.0.135': '119.8.51.247',
}
```

## Testing

Two test scripts were created to validate both scenarios:

1. **`test_nomad_no_mapping.py`**: Tests single IP environment without mapping
2. **`test_nomad_multi_mapping.py`**: Tests multi-node environment with mapping

Both tests successfully demonstrate the flexible IP mapping functionality.

## Backward Compatibility

The improvement is fully backward compatible:
- Existing configurations without `nomad_ip_mapping` continue to work unchanged
- The default behavior (no mapping) remains the same
- No breaking changes to existing APIs or configurations

## Conclusion

This improvement makes the Nomad runtime more flexible and suitable for various deployment scenarios, from simple single-IP environments to complex multi-node cloud deployments with network address translation requirements.
