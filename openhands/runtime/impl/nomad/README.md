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
export NOMAD_TOKEN="your-nomad-token"  # Optional, for ACL-enabled clusters
export NOMAD_NAMESPACE="openhands"     # Optional, default is "default"
export NOMAD_DATACENTER="dc1"          # Optional, default is "dc1"
```

### Configuration File

Add the following to your `config.toml`:

```toml
[sandbox]
# Use Nomad runtime
runtime = "nomad"

# Nomad cluster configuration
nomad_address = "http://your-nomad-cluster:4646"
nomad_token = "your-nomad-token"        # Optional
nomad_namespace = "openhands"           # Optional
nomad_datacenter = "dc1"                # Optional

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

## Performance Tuning

1. **Resource Allocation**: Adjust `nomad_cpu` and `nomad_memory` based on workload
2. **Placement**: Use Nomad constraints to place jobs on appropriate nodes
3. **Scaling**: Consider using Nomad's horizontal autoscaling for high-load scenarios
4. **Monitoring**: Integrate with Nomad's metrics and monitoring systems

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
