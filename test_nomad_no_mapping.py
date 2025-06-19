#!/usr/bin/env python3
"""
Test script for Nomad runtime without IP mapping (single IP environment).
This simulates an environment where Nomad returns public IPs directly.
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


async def test_nomad_no_mapping():
    """Test Nomad runtime without IP mapping."""
    print('Testing Nomad Runtime without IP mapping...')

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
    # NO IP mapping configured - should use original IPs
    # config.sandbox.nomad_ip_mapping = None  # This is the default

    # Create event stream
    config.file_store_path = '/tmp/test_nomad_no_mapping'
    file_store = get_file_store(
        config.file_store,
        config.file_store_path,
    )
    event_stream = EventStream('test-nomad-no-mapping', file_store)

    # Create runtime
    runtime = NomadRuntime(
        config=config,
        event_stream=event_stream,
        sid='test-nomad-no-mapping',
        plugins=[],
        env_vars={},
    )

    try:
        print('Creating Nomad job without IP mapping...')
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
        success = asyncio.run(test_nomad_no_mapping())
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
