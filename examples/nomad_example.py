#!/usr/bin/env python3
"""
Example script showing how to use OpenHands with Nomad runtime.

This script demonstrates:
1. Setting up configuration for Nomad runtime
2. Creating a runtime instance
3. Connecting to Nomad cluster
4. Running basic operations

Prerequisites:
- Nomad cluster running and accessible
- OpenHands runtime container image available to Nomad nodes
- Proper network connectivity between OpenHands and Nomad cluster
"""

import asyncio
import os

from openhands.core.config import OpenHandsConfig
from openhands.events import EventStream
from openhands.runtime import get_runtime_cls


async def main():
    """Main example function."""
    print('OpenHands Nomad Runtime Example')
    print('=' * 40)

    # Configuration for Nomad runtime
    config_dict = {
        'runtime': 'nomad',
        'sandbox': {
            'nomad_address': os.environ.get('NOMAD_ADDR', 'http://localhost:4646'),
            'nomad_token': os.environ.get('NOMAD_TOKEN'),  # Optional
            'nomad_namespace': os.environ.get('NOMAD_NAMESPACE', 'default'),
            'nomad_datacenter': os.environ.get('NOMAD_DATACENTER', 'dc1'),
            'nomad_cpu': 1000,  # 1 GHz
            'nomad_memory': 2048,  # 2 GB
            'runtime_container_image': 'openhands-runtime:latest',
            'runtime_startup_env_vars': {'EXAMPLE_VAR': 'example_value'},
        },
    }

    # Create configuration
    try:
        config = OpenHandsConfig(**config_dict)
        print('✓ Configuration created successfully')
        print(f'  - Nomad address: {config.sandbox.nomad_address}')
        print(f'  - Nomad namespace: {config.sandbox.nomad_namespace}')
        print(f'  - Container image: {config.sandbox.runtime_container_image}')
    except Exception as e:
        print(f'✗ Failed to create configuration: {e}')
        return

    # Get runtime class
    try:
        runtime_cls = get_runtime_cls('nomad')
        print(f'✓ Nomad runtime class loaded: {runtime_cls.__name__}')
    except Exception as e:
        print(f'✗ Failed to get runtime class: {e}')
        return

    # Create event stream (mock for this example)
    from openhands.storage.memory import InMemoryFileStore

    file_store = InMemoryFileStore()
    event_stream = EventStream('example-session', file_store)

    # Create runtime instance
    try:
        runtime = runtime_cls(
            config=config, event_stream=event_stream, sid='example-session-123'
        )
        print('✓ Runtime instance created')
        print(f'  - Session ID: {runtime.sid}')
        print(f'  - Job ID: {runtime.job_id}')
        print(f'  - Container image: {runtime.container_image}')
    except Exception as e:
        print(f'✗ Failed to create runtime instance: {e}')
        return

    # Test basic functionality
    print('\nTesting basic functionality:')

    # Test headers generation
    try:
        headers = runtime._get_nomad_headers()
        print(f'✓ Nomad headers generated: {list(headers.keys())}')
    except Exception as e:
        print(f'✗ Failed to generate headers: {e}')

    # Test job spec creation
    try:
        job_spec = runtime._create_job_spec()
        print('✓ Job specification created')
        print(f'  - Job ID: {job_spec["ID"]}')
        print(f'  - Job type: {job_spec["Type"]}')
        print(f'  - Datacenters: {job_spec["Datacenters"]}')
        print(f'  - Task groups: {len(job_spec["TaskGroups"])}')

        # Check GPU configuration
        task_groups = job_spec.get('TaskGroups', [])
        if task_groups:
            tasks = task_groups[0].get('Tasks', [])
            if tasks:
                task = tasks[0]
                resources = task.get('Resources', {})
                devices = resources.get('Devices')
                if devices:
                    print(f'  - GPU devices: {len(devices)} configured')
                    for device in devices:
                        print(f'    - {device["Name"]}: {device["Count"]} units')
                else:
                    print('  - GPU devices: None (GPU disabled)')
    except Exception as e:
        print(f'✗ Failed to create job spec: {e}')

    # Note: We don't actually connect to Nomad in this example
    # as it requires a real Nomad cluster
    print('\nNote: To actually connect to Nomad, call:')
    print('  await runtime.connect()')
    print('\nThis requires:')
    print('  - A running Nomad cluster')
    print('  - Network connectivity to Nomad API')
    print('  - Container image available to Nomad nodes')
    if config.sandbox.enable_gpu:
        print('  - GPU-enabled Nomad nodes with NVIDIA runtime')

    print('\nExample completed successfully!')


if __name__ == '__main__':
    asyncio.run(main())
