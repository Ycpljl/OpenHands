# OpenHands Nomad Runtime

This document describes the HashiCorp Nomad runtime implementation for OpenHands, which allows deploying OpenHands runtime environments on Nomad clusters.

## Overview

The Nomad runtime enables OpenHands to orchestrate sandbox environments using HashiCorp Nomad, providing:

- **Container Orchestration**: Leverages Nomad's job scheduling and container management
- **Dynamic Resource Allocation**: Automatic CPU, memory, and port allocation
- **Network Isolation**: Uses Nomad bridge networking for secure container networking
- **Scalability**: Can scale across multiple Nomad nodes and datacenters
- **High Availability**: Benefits from Nomad's built-in fault tolerance

## Configuration

### Required Configuration

Add the following to your OpenHands configuration:

```yaml
runtime: nomad
sandbox:
  nomad_address: "http://your-nomad-cluster:4646"
  nomad_token: "your-nomad-token"
  nomad_datacenter: "your-datacenter"
  nomad_namespace: "default"
  runtime_container_image: "ghcr.io/all-hands-ai/runtime:0.43-nikolaik"
```

### Configuration Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `nomad_address` | string | Required | Nomad cluster HTTP API address |
| `nomad_token` | string | Required | Nomad authentication token |
| `nomad_datacenter` | string | Required | Target Nomad datacenter |
| `nomad_namespace` | string | `"default"` | Nomad namespace for jobs |
| `nomad_job_cpu` | int | `1000` | CPU allocation in MHz |
| `nomad_job_memory` | int | `2048` | Memory allocation in MB |
| `nomad_ip_mapping` | dict | `None` | IP address mapping for cloud environments |

### Example Configuration

```python
from openhands.core.config import OpenHandsConfig

config = OpenHandsConfig()
config.runtime = 'nomad'
config.sandbox.nomad_address = 'http://nomad.example.com:4646'
config.sandbox.nomad_token = 'your-secret-token'
config.sandbox.nomad_datacenter = 'dc1'
config.sandbox.nomad_namespace = 'openhands'
config.sandbox.nomad_job_cpu = 2000
config.sandbox.nomad_job_memory = 4096
# Configure IP mapping for cloud environments
config.sandbox.nomad_ip_mapping = {
    '192.168.0.133': '119.8.51.245',  # Map internal IP to external IP
    '10.0.1.100': '203.0.113.10'      # Additional mappings as needed
}
```

## Architecture

### Job Structure

The Nomad runtime creates jobs with the following structure:

```hcl
job "openhands-runtime-{session-id}" {
  datacenters = ["your-datacenter"]
  namespace   = "your-namespace"

  group "runtime" {
    network {
      mode = "bridge"
      port "http" {
        to = 8080
      }
    }

    task "sandbox" {
      driver = "docker"

      config {
        image = "ghcr.io/all-hands-ai/runtime:0.43-nikolaik"
        ports = ["http"]
        command = "/openhands/micromamba/bin/micromamba"
        args = [
          "run", "-n", "openhands", "poetry", "run",
          "python", "-u", "-m", "openhands.runtime.action_execution_server",
          "8080", "--working-dir", "/workspace",
          "--username", "openhands", "--user-id", "1000"
        ]
        work_dir = "/openhands/code"
      }

      resources {
        cpu    = 1000  # Configurable
        memory = 2048  # Configurable
      }
    }
  }
}
```

### Networking

- **Bridge Mode**: Uses Nomad bridge networking for container isolation
- **Dynamic Ports**: Automatically allocates available ports on the host
- **Port Mapping**: Maps container port 8080 to a dynamic host port
- **External Access**: Supports IP address translation for cloud environments

#### IP Address Mapping for Different Network Environments

The Nomad runtime supports flexible IP address handling to accommodate different network environments:

##### Scenario 1: Single IP Environment (No Mapping Needed)

**Use Case**: Nomad cluster uses public IPs directly, or you're accessing from within the same network.

**Configuration**: Simply omit the `nomad_ip_mapping` field or set it to `null`:

```yaml
sandbox:
  nomad_address: "http://203.0.113.10:4646"  # Direct public IP
  # No nomad_ip_mapping needed
```

**Behavior**: The runtime uses the original IP addresses returned by Nomad directly.

##### Scenario 2: Multi-Node Environment with IP Mapping

**Use Case**: Cloud environments where Nomad returns internal/private IP addresses that need to be mapped to external/public IPs.

**Configuration**: Define mappings for each node that requires translation:

```yaml
sandbox:
  nomad_ip_mapping:
    "192.168.0.133": "119.8.51.245"  # Node 1: internal -> external
    "192.168.0.134": "119.8.51.246"  # Node 2: internal -> external
    "192.168.0.135": "119.8.51.247"  # Node 3: internal -> external
```

**Behavior**:
- IPs listed in the mapping are translated to their external counterparts
- IPs not in the mapping use their original values
- This allows mixed environments where some nodes need mapping and others don't

##### How IP Mapping Works

1. **Job Allocation**: Nomad allocates a job and returns the node IP address
2. **Mapping Check**: The runtime checks if the IP exists in the `nomad_ip_mapping` configuration
3. **Conditional Translation**:
   - If mapping exists: Replace internal IP with configured external IP
   - If no mapping: Use the original IP address
4. **URL Construction**: Build the final runtime URL with the appropriate IP

##### Examples

**Without mapping**:
- Nomad returns: `http://203.0.113.10:30084`
- Final URL: `http://203.0.113.10:30084` (unchanged)

**With mapping**:
- Nomad returns: `http://192.168.0.133:30084`
- Mapping: `"192.168.0.133": "119.8.51.245"`
- Final URL: `http://119.8.51.245:30084` (mapped)

**Mixed environment**:
- Node A returns: `http://192.168.0.133:30084` → `http://119.8.51.245:30084` (mapped)
- Node B returns: `http://203.0.113.20:30085` → `http://203.0.113.20:30085` (no mapping, unchanged)

This flexible approach ensures compatibility with various network architectures while maintaining simplicity for straightforward deployments.

### Lifecycle Management

1. **Job Creation**: Creates a new Nomad job for each runtime session
2. **Allocation Monitoring**: Waits for job allocation and tracks status
3. **Service Discovery**: Extracts host IP and port for external access
4. **Health Monitoring**: Continuously monitors job and allocation health
5. **Cleanup**: Stops and removes jobs when runtime is closed

## Usage

### Basic Usage

```python
import asyncio
from openhands.core.config import OpenHandsConfig
from openhands.events import EventStream
from openhands.runtime.impl.nomad.nomad_runtime import NomadRuntime
from openhands.storage import get_file_store

async def main():
    # Configure for Nomad
    config = OpenHandsConfig()
    config.runtime = 'nomad'
    config.sandbox.nomad_address = 'http://nomad.example.com:4646'
    config.sandbox.nomad_token = 'your-token'
    config.sandbox.nomad_datacenter = 'dc1'

    # Create event stream
    file_store = get_file_store(config.file_store, config.file_store_path)
    event_stream = EventStream('session-id', file_store)

    # Create and connect runtime
    runtime = NomadRuntime(
        config=config,
        event_stream=event_stream,
        sid='session-id',
        plugins=[]
    )

    try:
        await runtime.connect()
        print(f"Runtime URL: {runtime.runtime_url}")

        # Use runtime for actions...

    finally:
        runtime.close()

asyncio.run(main())
```

### With OpenHands Agent

```python
from openhands.core.config import OpenHandsConfig
from openhands.core.main import create_runtime

# Configure for Nomad
config = OpenHandsConfig()
config.runtime = 'nomad'
config.sandbox.nomad_address = 'http://nomad.example.com:4646'
config.sandbox.nomad_token = 'your-token'
config.sandbox.nomad_datacenter = 'dc1'

# Create runtime (automatically uses Nomad)
runtime = create_runtime(config)
```

## Requirements

### Nomad Cluster Requirements

- **Nomad Version**: 1.4+ recommended
- **Docker Driver**: Enabled on client nodes
- **CNI Plugins**: Bridge networking support required
- **Network Access**: HTTP API access to Nomad cluster

### Required CNI Plugins

The Nomad runtime requires the following CNI plugins (version 0.4.0+):
- `bridge`
- `firewall`
- `host-local`
- `loopback`
- `portmap`

### Container Image Requirements

- **Base Image**: `ghcr.io/all-hands-ai/runtime:0.43-nikolaik`
- **Architecture**: Must match Nomad client architecture
- **Availability**: Image must be accessible from Nomad client nodes

## Troubleshooting

### Common Issues

#### Job Fails to Start

**Symptoms**: Job allocation fails or containers exit immediately

**Solutions**:
1. Check Nomad client logs: `nomad alloc logs <alloc-id>`
2. Verify container image is available
3. Check resource constraints (CPU/memory)
4. Ensure CNI plugins are properly configured

#### Network Connectivity Issues

**Symptoms**: Cannot connect to runtime URL

**Solutions**:
1. Verify port mapping in allocation details
2. Check firewall rules on Nomad clients
3. Ensure bridge networking is configured
4. Verify IP address translation settings

#### Authentication Errors

**Symptoms**: 403 Forbidden or authentication failures

**Solutions**:
1. Verify Nomad token has required permissions
2. Check token expiration
3. Ensure namespace access permissions
4. Verify datacenter access

### Debugging

#### Check Job Status

```bash
# List jobs
nomad job status

# Check specific job
nomad job status openhands-runtime-{session-id}

# View allocation details
nomad alloc status <allocation-id>

# View logs
nomad alloc logs <allocation-id> sandbox
```

#### Monitor Runtime Logs

```bash
# View stderr logs
nomad alloc logs <allocation-id> sandbox stderr

# View stdout logs
nomad alloc logs <allocation-id> sandbox stdout

# Follow logs in real-time
nomad alloc logs -f <allocation-id> sandbox
```

## Security Considerations

### Network Security

- **Isolation**: Each runtime runs in an isolated network namespace
- **Port Binding**: Only necessary ports are exposed
- **Firewall**: Configure appropriate firewall rules for Nomad clients

### Access Control

- **Token Permissions**: Use least-privilege Nomad tokens
- **Namespace Isolation**: Use dedicated namespaces for OpenHands workloads
- **Resource Limits**: Set appropriate CPU and memory limits

### Container Security

- **User Privileges**: Runs as non-root user (UID 1000)
- **Read-only Filesystem**: Consider using read-only root filesystem
- **Security Policies**: Apply Nomad security policies as needed

## Performance Tuning

### Resource Allocation

```yaml
sandbox:
  nomad_job_cpu: 2000     # 2 CPU cores
  nomad_job_memory: 4096  # 4GB RAM
```

### Placement Constraints

Add constraints to the job specification for specific placement:

```hcl
constraint {
  attribute = "${attr.kernel.name}"
  value     = "linux"
}

constraint {
  attribute = "${node.class}"
  value     = "compute"
}
```

### Scaling Considerations

- **Node Capacity**: Ensure sufficient resources on Nomad clients
- **Image Caching**: Pre-pull images on nodes for faster startup
- **Network Bandwidth**: Consider network capacity for concurrent runtimes

## Monitoring

### Metrics

Monitor the following metrics:
- Job success/failure rates
- Allocation startup times
- Resource utilization (CPU, memory)
- Network connectivity

### Logging

The runtime provides structured logging with the following fields:
- `session_id`: Runtime session identifier
- `job_id`: Nomad job identifier
- `allocation_id`: Nomad allocation identifier
- `severity`: Log level (INFO, ERROR, etc.)
- `message`: Human-readable message

### Health Checks

The runtime continuously monitors:
- Job status and health
- Allocation status
- Network connectivity
- Service availability

## References

- [HashiCorp Nomad Documentation](https://developer.hashicorp.com/nomad)
- [Nomad API Reference](https://developer.hashicorp.com/nomad/api-docs)
- [Nomad Networking Guide](https://developer.hashicorp.com/nomad/docs/networking)
- [OpenHands Runtime Architecture](https://docs.all-hands.dev/usage/architecture/runtime)
