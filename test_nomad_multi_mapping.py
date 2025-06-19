#!/usr/bin/env python3
"""
Test script for Nomad runtime with multi-node IP mapping.
This simulates an environment with multiple nodes requiring different IP mappings.
"""

import asyncio
import logging
import signal
import sys

from openhands.core.config import OpenHandsConfig
from openhands.events.stream import EventStream
from openhands.runtime.impl.nomad.nomad_runtime import NomadRuntime
from openhands.storage import get_file_store

# Configure logging
logging.basicConfig(level=logging.INFO)


async def test_nomad_multi_mapping():
    """Test Nomad runtime with multi-node IP mapping."""
    print('Testing Nomad Runtime with multi-node IP mapping...')

    # Configure OpenHands for Nomad runtime
    config = OpenHandsConfig()
    config.runtime = 'nomad'
    config.sandbox.nomad_address = 'http://119.8.51.245:4646'
    config.sandbox.nomad_token = '72b2d656-024e-5bc5-ba5a-b598c27f7c2e'
    config.sandbox.nomad_datacenter = 'langcode_1'
    config.sandbox.nomad_namespace = 'default'
    config.sandbox.runtime_container_image = (
        'ghcr.io/all-hands-ai/runtime:0.43-nikolaik'
    )
    # Configure multi-node IP mapping
    config.sandbox.nomad_ip_mapping = {
        '192.168.0.133': '119.8.51.245',  # Node 1: internal -> external
        '192.168.0.134': '119.8.51.246',  # Node 2: internal -> external
        '192.168.0.135': '119.8.51.247',  # Node 3: internal -> external
        '10.0.1.100': '203.0.113.10',  # Node 4: different subnet
        # Note: If a job lands on an unmapped node, it will use the original IP
    }

    # Create event stream
    config.file_store_path = '/tmp/test_nomad_multi_mapping'
    file_store = get_file_store(
        config.file_store,
        config.file_store_path,
    )
    event_stream = EventStream('test-nomad-multi-mapping', file_store)

    # Create runtime
    runtime = NomadRuntime(
        config=config,
        event_stream=event_stream,
        sid='test-nomad-multi-mapping',
        plugins=[],
        env_vars={},
    )

    try:
        print('Creating Nomad job with multi-node IP mapping...')
        print('Configured mappings:')
        for internal, external in config.sandbox.nomad_ip_mapping.items():
            print(f'  {internal} -> {external}')

        await runtime.connect()

        print('✅ Job created successfully!')
        print(f'Runtime URL: {runtime.runtime_url}')

        # Wait a bit to see the logs
        await asyncio.sleep(10)

        return True

    except Exception as e:
        print(f'❌ Error: {e}')
        return False
    finally:
        print('Cleaning up...')
        try:
            await runtime.disconnect()
        except Exception as e:
            print(f'Cleanup error: {e}')


def signal_handler(signum, frame):
    """Handle interrupt signals."""
    print('\nReceived interrupt signal, exiting...')
    sys.exit(0)


if __name__ == '__main__':
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        success = asyncio.run(test_nomad_multi_mapping())
        if success:
            print('✅ Test completed successfully!')
        else:
            print('❌ Test failed!')
            sys.exit(1)
    except KeyboardInterrupt:
        print('\nTest interrupted by user')
        sys.exit(130)
    except Exception as e:
        print(f'❌ Unexpected error: {e}')
        sys.exit(1)
