#!/usr/bin/env python3

import asyncio
import sys
from pathlib import Path

# Add the OpenHands directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from openhands.core.config import OpenHandsConfig
from openhands.events import EventStream
from openhands.runtime.impl.nomad.nomad_runtime import NomadRuntime
from openhands.storage import get_file_store


async def test_nomad_simple():
    """Simple test for Nomad runtime - just verify job creation and deployment."""

    # Create config
    config = OpenHandsConfig()
    config.runtime = 'nomad'
    config.sandbox.nomad_address = 'http://119.8.51.245:4646'
    config.sandbox.nomad_token = '72b2d656-024e-5bc5-ba5a-b598c27f7c2e'
    config.sandbox.nomad_datacenter = 'langcode_1'
    config.sandbox.nomad_namespace = 'default'
    config.sandbox.runtime_container_image = (
        'ghcr.io/all-hands-ai/runtime:0.43-nikolaik'
    )
    # Configure IP mapping for cloud environment
    config.sandbox.nomad_ip_mapping = {
        '192.168.0.133': '119.8.51.245'  # Map internal IP to external IP
    }

    # Create event stream
    file_store = get_file_store(
        config.file_store,
        config.file_store_path,
        config.file_store_web_hook_url,
        config.file_store_web_hook_headers,
    )
    event_stream = EventStream('test-nomad-simple', file_store)

    # Create runtime
    runtime = NomadRuntime(
        config=config,
        event_stream=event_stream,
        sid='test-nomad-simple',
        plugins=[],
    )

    try:
        print('Testing Nomad Runtime Job Creation...')

        # Connect (this creates the job)
        print('Creating Nomad job...')
        await runtime.connect()

        print('✅ Job created successfully!')
        print(f'   Job ID: {runtime.job_id}')
        print(f'   Allocation ID: {runtime.allocation_id}')
        print(f'   Runtime URL: {runtime.runtime_url}')

        # Wait a bit for the job to start
        print('Waiting for job to start...')
        await asyncio.sleep(10)

        # Check if we can get the runtime status
        try:
            status = runtime.status
            print(f'   Runtime Status: {status}')
        except Exception as e:
            print(f'   Status check failed (expected): {e}')

        print('✅ Nomad runtime deployment test completed successfully!')

    except Exception as e:
        print(f'❌ Test failed: {e}')
        import traceback

        traceback.print_exc()
        return False
    finally:
        print('Cleaning up...')
        try:
            runtime.close()
        except Exception:
            pass

    return True


if __name__ == '__main__':
    success = asyncio.run(test_nomad_simple())
    sys.exit(0 if success else 1)
