# Nomad Runtime

The Nomad Runtime allows OpenHands to use HashiCorp Nomad for container orchestration, providing better scalability and resource management in distributed environments.

## Overview

The Nomad Runtime creates and manages Docker containers through Nomad's API instead of directly using Docker. This enables:

- **Scalability**: Distribute OpenHands tasks across multiple nodes in a Nomad cluster
- **Resource Management**: Better CPU and memory allocation through Nomad's scheduler
- **High Availability**: Automatic failover and rescheduling of failed containers
- **Multi-tenancy**: Isolation and resource quotas through Nomad namespaces

## Prerequisites

1. **Nomad Cluster**: A running Nomad cluster with Docker driver enabled
2. **Docker Images**: The OpenHands runtime container images must be available to Nomad nodes
3. **Network Access**: OpenHands server must be able to reach Nomad API and allocated containers

## Configuration

### Environment Variables

You can configure the Nomad runtime using environment variables:

```bash
export NOMAD_ADDR="http://your-nomad-cluster:4646"
export NOMAD_TOKEN="your-nomad-token"              # Optional, for ACL-enabled clusters
export NOMAD_NAMESPACE="openhands"                 # Optional, default is "default"
export NOMAD_DATACENTER="dc1"                      # Optional, default is "dc1"
export NOMAD_ENABLE_SERVICE_DISCOVERY="true"       # Optional, default is "true"
```

### Service Discovery Configuration

By default, the Nomad runtime enables service discovery and health checks through Consul integration. This requires Consul to be available and properly configured with your Nomad cluster.

**If you don't have Consul or want to disable service discovery:**

```bash
export NOMAD_ENABLE_SERVICE_DISCOVERY="false"
```

**Note**: Disabling service discovery will:
- Remove the Consul version constraint (`${attr.consul.version} semver >= 1.8.0`)
- Disable automatic health checks
- Allow jobs to run on nodes without Consul

### Configuration File

Add the following to your `config.toml`:

```toml
[sandbox]
# Use Nomad runtime
runtime = "nomad"

# Nomad cluster configuration
nomad_address = "http://your-nomad-cluster:4646"
nomad_token = "your-nomad-token"                    # Optional
nomad_namespace = "openhands"                       # Optional
nomad_datacenter = "dc1"                            # Optional

# Service discovery (Consul integration)
nomad_enable_service_discovery = false              # Optional, default is true

# Resource allocation
nomad_cpu = 1000      # CPU in MHz, default 1000
nomad_memory = 2048   # Memory in MB, default 2048

# Container image
runtime_container_image = "your-registry/openhands-runtime:latest"
```

## Usage

### Basic Usage

```python
from openhands.core.config import OpenHandsConfig
from openhands.runtime import get_runtime_cls

# Create configuration
config = OpenHandsConfig(
    sandbox={
        'runtime': 'nomad',
        'nomad_address': 'http://localhost:4646',
        'runtime_container_image': 'openhands-runtime:latest'
    }
)

# Get runtime class and create instance
runtime_cls = get_runtime_cls('nomad')
runtime = runtime_cls(config, event_stream, sid='my-session')

# Connect and use
await runtime.connect()
```

### Command Line

```bash
# Set environment variables
export NOMAD_ADDR="http://localhost:4646"

# Run OpenHands with Nomad runtime
python -m openhands.cli.main \
    --runtime nomad \
    --runtime-container-image openhands-runtime:latest \
    --task "Create a simple Python script"
```

## Nomad Job Specification

The runtime creates Nomad jobs with the following characteristics:

- **Job Type**: Service (long-running)
- **Driver**: Docker
- **Restart Policy**: 3 attempts with exponential backoff
- **Health Checks**: HTTP health check on `/health` endpoint
- **Service Discovery**: Automatic service registration with tags
- **Resource Allocation**: Configurable CPU and memory limits
- **GPU Support**: Optional GPU device allocation

### Example Job Spec

```hcl
job "openhands-runtime-session-123" {
  type = "service"
  datacenters = ["dc1"]
  namespace = "openhands"

  group "runtime" {
    count = 1

    restart {
      attempts = 3
      interval = "5m"
      delay = "25s"
      mode = "fail"
    }

    task "action-server" {
      driver = "docker"

      config {
        image = "openhands-runtime:latest"
        command = "/openhands/micromamba/bin/python"
        args = ["-m", "openhands.runtime.action_execution_server"]
        work_dir = "/openhands/code/"
        port_map {
          action_server = 60000
        }
      }

      resources {
        cpu = 1000
        memory = 2048
        network {
          mbits = 10
          port "action_server" {}
        }
      }

      service {
        name = "openhands-runtime-session-123"
        port = "action_server"
        tags = ["openhands", "runtime", "session-123"]

        check {
          type = "http"
          path = "/health"
          interval = "10s"
          timeout = "3s"
        }
      }
    }
  }
}
```

## Features

### Supported Features

- ✅ Container lifecycle management (start, stop, restart)
- ✅ Dynamic port allocation
- ✅ Service discovery and health checks
- ✅ Resource constraints (CPU, memory)
- ✅ GPU support (when available)
- ✅ Environment variable injection
- ✅ Automatic cleanup on session end
- ✅ Attach to existing jobs

### Limitations

- ❌ VSCode integration (requires additional setup)
- ❌ Volume mounts (Nomad doesn't support Docker-style volume mounts)
- ❌ Host networking mode
- ❌ Custom network configurations

## Troubleshooting

### Common Issues

1. **Job Fails to Start**
   - Check if Docker driver is enabled on Nomad clients
   - Verify container image is accessible from Nomad nodes
   - Check resource availability (CPU, memory)

2. **Connection Timeout**
   - Verify network connectivity between OpenHands and Nomad nodes
   - Check firewall rules for dynamic port ranges
   - Ensure health checks are passing

3. **Permission Denied**
   - Verify Nomad token has required permissions
   - Check namespace access rights
   - Ensure Docker daemon is accessible to Nomad

### Debugging

Enable debug logging:

```python
import logging
logging.getLogger('openhands.runtime.impl.nomad').setLevel(logging.DEBUG)
```

Check Nomad job status:

```bash
nomad job status openhands-runtime-session-123
nomad alloc logs <allocation-id>
```

## Security Considerations

1. **Network Security**: Ensure proper firewall rules for Nomad cluster communication
2. **Token Management**: Use least-privilege Nomad tokens
3. **Image Security**: Use trusted container images and registries
4. **Resource Limits**: Set appropriate CPU and memory limits to prevent resource exhaustion

## GPU Support

The Nomad runtime provides comprehensive GPU support with fine-grained control over GPU allocation and configuration.

### Basic GPU Configuration

```toml
[sandbox]
enable_gpu = true
```

### Advanced GPU Configuration

```toml
[sandbox]
enable_gpu = true
nomad_gpu_count = 2                    # Number of GPUs to allocate (default: 1)
nomad_gpu_type = "nvidia/tesla-v100"   # Specific GPU type (default: "nvidia/gpu")
```

### GPU Configuration Options

- **`enable_gpu`**: Enable GPU support (default: false)
- **`nomad_gpu_count`**: Number of GPUs to allocate (default: 1 when GPU enabled)
- **`nomad_gpu_type`**: GPU type constraint for specific GPU models:
  - `"nvidia/gpu"` - Any NVIDIA GPU (default)
  - `"nvidia/tesla-v100"` - NVIDIA Tesla V100
  - `"nvidia/tesla-k80"` - NVIDIA Tesla K80
  - `"nvidia/geforce-rtx-3080"` - NVIDIA GeForce RTX 3080
  - Custom GPU types as configured in your Nomad cluster

### What GPU Support Includes

When GPU support is enabled, the runtime automatically:

1. **Resource Allocation**: Requests the specified number and type of GPUs from Nomad
2. **Docker Configuration**:
   - Enables NVIDIA Docker runtime
   - Mounts GPU device files (`/dev/nvidia*`, `/dev/nvidiactl`, `/dev/nvidia-uvm`)
   - Adds necessary capabilities (`SYS_ADMIN`)
3. **Environment Variables**:
   - `NVIDIA_VISIBLE_DEVICES=all`
   - `NVIDIA_DRIVER_CAPABILITIES=compute,utility`
   - `CUDA_VISIBLE_DEVICES=all`
4. **Node Constraints**: Ensures jobs are scheduled only on nodes with NVIDIA Docker runtime

### Prerequisites for GPU Support

**Nomad Cluster Requirements:**
- Nomad nodes with NVIDIA GPU drivers installed
- NVIDIA Docker runtime configured on GPU nodes
- Nomad device plugin for NVIDIA GPUs enabled
- Proper GPU device detection in Nomad

**Nomad Configuration Example:**
```hcl
# nomad.hcl
client {
  enabled = true

  # Enable device plugins
  options {
    "driver.allowlist" = "docker"
  }
}

plugin "nvidia-gpu" {
  config {
    enabled = true
    ignore_topology = false
  }
}
```

**Docker Configuration on Nomad Nodes:**
```json
{
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  }
}
```

### GPU Usage Examples

**Single GPU for Machine Learning:**
```toml
[sandbox]
enable_gpu = true
nomad_gpu_count = 1
runtime_container_image = "tensorflow/tensorflow:latest-gpu"
```

**Multiple GPUs for Distributed Training:**
```toml
[sandbox]
enable_gpu = true
nomad_gpu_count = 4
nomad_gpu_type = "nvidia/tesla-v100"
runtime_container_image = "pytorch/pytorch:latest"
```

**Specific GPU Model for Inference:**
```toml
[sandbox]
enable_gpu = true
nomad_gpu_count = 1
nomad_gpu_type = "nvidia/geforce-rtx-3080"
runtime_container_image = "nvcr.io/nvidia/pytorch:latest"
```

## Performance Tuning

1. **Resource Allocation**: Adjust `nomad_cpu` and `nomad_memory` based on workload
2. **GPU Allocation**: Configure `nomad_gpu_count` and `nomad_gpu_type` for optimal GPU utilization
3. **Placement**: Use Nomad constraints to place jobs on appropriate nodes
4. **Scaling**: Consider using Nomad's horizontal autoscaling for high-load scenarios
5. **Monitoring**: Integrate with Nomad's metrics and monitoring systems

## Integration with CI/CD

The Nomad runtime can be integrated with CI/CD pipelines for automated testing and deployment:

```yaml
# GitHub Actions example
- name: Run OpenHands Tests
  env:
    NOMAD_ADDR: ${{ secrets.NOMAD_ADDR }}
    NOMAD_TOKEN: ${{ secrets.NOMAD_TOKEN }}
  run: |
    python -m openhands.cli.main \
      --runtime nomad \
      --runtime-container-image ${{ env.RUNTIME_IMAGE }} \
      --task "Run test suite"
```

## Troubleshooting

### Common Issues

#### 1. Connection Refused Error

**Problem**: `[Errno 61] Connection refused` when connecting to runtime container.

**Causes**:
- Network configuration issues
- Port mapping problems
- Nomad version compatibility

**Solutions**:
- Ensure you're using a modern Nomad version (1.4+)
- Verify network mode is set to `bridge`
- Check that dynamic ports are properly configured
- Disable service discovery if Consul is not available:
  ```toml
  [sandbox]
  nomad_enable_service_discovery = false
  ```

#### 2. Consul Version Constraint Error

**Problem**: `Constraint ${attr.consul.version} semver >= 1.8.0 filtered 1 node`

**Solution**: Disable service discovery if Consul is not available:
```bash
export NOMAD_ENABLE_SERVICE_DISCOVERY="false"
```
Or in config.toml:
```toml
[sandbox]
nomad_enable_service_discovery = false
```

#### 3. Job Placement Failures

**Problem**: Jobs fail to be placed on any nodes.

**Solutions**:
- Check node eligibility: `nomad node status`
- Verify resource requirements don't exceed available resources
- Review job constraints and node attributes
- Check Docker driver is enabled on nodes

#### 4. Container Image Pull Failures

**Problem**: Nomad cannot pull the container image.

**Solutions**:
- Ensure image exists and is accessible from Nomad nodes
- Configure Docker registry authentication if needed
- Use fully qualified image names (registry/namespace/image:tag)

### Debugging Commands

```bash
# Check job status
nomad job status openhands-runtime-<session-id>

# View job logs
nomad alloc logs <allocation-id>

# Check node status
nomad node status

# View allocation details
nomad alloc status <allocation-id>

# Monitor job events
nomad job history openhands-runtime-<session-id>
```
