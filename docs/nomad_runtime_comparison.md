# Nomad Runtime vs Docker Runtime Feature Comparison

This document provides a comprehensive comparison between the Docker Runtime and Nomad Runtime implementations in OpenHands.

## Overview

The Nomad Runtime provides an alternative to Docker Runtime for running OpenHands sandboxes in HashiCorp Nomad clusters. It offers similar functionality while leveraging Nomad's orchestration capabilities.

## Feature Comparison Matrix

| Feature | Docker Runtime | Nomad Runtime | Status | Notes |
|---------|----------------|---------------|---------|-------|
| **Container Lifecycle Management** |
| Create containers | ✅ | ✅ | Complete | Uses Nomad jobs instead of direct Docker |
| Start containers | ✅ | ✅ | Complete | Automatic with job submission |
| Stop containers | ✅ | ✅ | Complete | Job stop functionality |
| Delete containers | ✅ | ✅ | Complete | Job purge functionality |
| Attach to existing containers | ✅ | ✅ | Complete | Job reattachment by ID |
| **Networking** |
| Port management | ✅ | ✅ | Complete | Dynamic port allocation |
| Host networking | ✅ | ❌ | Not supported | Nomad uses bridge mode |
| Bridge networking | ✅ | ✅ | Complete | Default mode in Nomad |
| IP mapping | ❌ | ✅ | Enhanced | Cloud environment support |
| **Resource Management** |
| CPU limits | ✅ | ✅ | Complete | Configurable CPU allocation |
| Memory limits | ✅ | ✅ | Complete | Configurable memory allocation |
| GPU support | ✅ | ❌ | Not implemented | Planned for future release |
| **Storage** |
| Volume mounting | ✅ | ❌ | Not implemented | Planned for future release |
| Bind mounts | ✅ | ❌ | Not implemented | Planned for future release |
| Workspace mounting | ✅ | ❌ | Not implemented | Planned for future release |
| **Environment Variables** |
| Basic env vars | ✅ | ✅ | Complete | Full support |
| Runtime-specific vars | ✅ | ✅ | Enhanced | Nomad-specific variables added |
| Debug mode support | ✅ | ✅ | Complete | Debug flag propagation |
| **Logging** |
| Container logs | ✅ | ✅ | Complete | Via Nomad logs API |
| Log streaming | ✅ | ✅ | Complete | Real-time log streaming |
| Log filtering | ✅ | ✅ | Complete | stdout/stderr separation |
| **Health Checking** |
| Container health | ✅ | ✅ | Complete | Uses `/alive` endpoint |
| Readiness checks | ✅ | ✅ | Complete | Wait for job running |
| **Job Control** |
| Pause/Resume | ❌ | ✅ | Enhanced | Nomad-specific feature |
| Job status monitoring | ❌ | ✅ | Enhanced | Real-time job status |
| **Integration** |
| VSCode support | ✅ | ✅ | Complete | VSCode server URL generation |
| Plugin support | ✅ | ✅ | Complete | Plugin loading |
| **Error Handling** |
| Retry mechanisms | ✅ | ✅ | Complete | Configurable retries |
| Error reporting | ✅ | ✅ | Complete | Detailed error messages |
| **Configuration** |
| Runtime configuration | ✅ | ✅ | Complete | Nomad-specific config options |
| Security options | ✅ | ✅ | Complete | Token-based authentication |

## Nomad Runtime Specific Features

### 1. IP Mapping
The Nomad Runtime includes IP mapping functionality to handle cloud environments where internal IPs need to be mapped to external IPs:

```python
config.sandbox.nomad_ip_mapping = {
    '192.168.0.133': '119.8.51.245',  # internal -> external
}
```

### 2. Enhanced Environment Variables
Additional environment variables specific to Nomad:

- `OPENHANDS_RUNTIME`: Set to "nomad"
- `OPENHANDS_NOMAD_JOB_ID`: Current Nomad job ID
- `OPENHANDS_NOMAD_ALLOCATION_ID`: Current allocation ID
- Standard Nomad environment variables (NOMAD_JOB_ID, NOMAD_ALLOC_ID, etc.)

### 3. Pause/Resume Functionality
Unique to Nomad Runtime:

```python
runtime.pause()   # Stop the job
runtime.resume()  # Restart the job
```

### 4. Log Streaming
Enhanced log access:

```python
# Get recent logs
logs = runtime.get_logs(tail=100)

# Stream logs in real-time
for line in runtime.stream_logs(follow=True):
    print(line)
```

## Configuration Examples

### Docker Runtime Configuration
```python
config = OpenHandsConfig()
config.runtime = 'docker'
config.sandbox.runtime_container_image = 'ghcr.io/all-hands-ai/runtime:0.43-nikolaik'
config.sandbox.enable_gpu = True
config.sandbox.volumes = '/host/path:/container/path:rw'
```

### Nomad Runtime Configuration
```python
config = OpenHandsConfig()
config.runtime = 'nomad'
config.sandbox.nomad_address = 'http://nomad.example.com:4646'
config.sandbox.nomad_token = 'your-nomad-token'
config.sandbox.nomad_datacenter = 'dc1'
config.sandbox.nomad_namespace = 'default'
config.sandbox.runtime_container_image = 'ghcr.io/all-hands-ai/runtime:0.43-nikolaik'
config.sandbox.nomad_ip_mapping = {
    '192.168.1.100': '203.0.113.1',
}
```

## Migration Guide

### From Docker to Nomad

1. **Update configuration**:
   - Change `config.runtime` from 'docker' to 'nomad'
   - Add Nomad-specific configuration options
   - Configure IP mapping if needed

2. **Remove unsupported features**:
   - Volume mounts (temporarily)
   - GPU support (temporarily)
   - Host networking

3. **Update environment variables**:
   - Use `OPENHANDS_RUNTIME` instead of Docker-specific vars
   - Access Nomad-specific variables

4. **Test functionality**:
   - Verify job creation and management
   - Test log access and streaming
   - Validate pause/resume if needed

## Performance Considerations

### Docker Runtime
- Direct container management
- Lower overhead for single-node deployments
- Immediate container operations

### Nomad Runtime
- Orchestration overhead
- Better for multi-node clusters
- Automatic scheduling and placement
- Built-in service discovery
- Enhanced monitoring and logging

## Future Roadmap

### Planned Features for Nomad Runtime

1. **Volume Support**
   - Bind mounts
   - Named volumes
   - Workspace mounting

2. **GPU Support**
   - Nomad device plugins
   - GPU resource allocation
   - CUDA support

3. **Advanced Networking**
   - Service mesh integration
   - Load balancing
   - Multi-datacenter support

4. **Enhanced Security**
   - Vault integration
   - ACL policies
   - Secure variable handling

## Conclusion

The Nomad Runtime provides a robust alternative to Docker Runtime with enhanced orchestration capabilities. While some features are not yet implemented (volumes, GPU), the core functionality is complete and production-ready.

Choose Nomad Runtime when:
- Running in a Nomad cluster
- Need orchestration features
- Require multi-node deployments
- Want enhanced monitoring and logging

Choose Docker Runtime when:
- Running on single nodes
- Need volume mounting
- Require GPU support
- Want minimal overhead
