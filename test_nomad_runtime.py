#!/usr/bin/env python3
"""Test script for the Nomad runtime implementation."""

import asyncio
import sys
from pathlib import Path

# Add the OpenHands directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from openhands.core.config import OpenHandsConfig
from openhands.events import EventStream
from openhands.events.action import CmdRunAction
from openhands.runtime.impl.nomad.nomad_runtime import NomadRuntime
from openhands.storage import get_file_store


async def test_nomad_runtime():
    """Test the Nomad runtime implementation."""
    print('Testing Nomad Runtime...')

    # Create configuration
    config = OpenHandsConfig()
    config.sandbox.nomad_address = 'http://119.8.51.245:4646'
    config.sandbox.nomad_token = '72b2d656-024e-5bc5-ba5a-b598c27f7c2e'
    config.sandbox.nomad_datacenter = 'langcode_1'
    config.sandbox.nomad_namespace = 'default'
    config.sandbox.runtime_container_image = (
        'ghcr.io/all-hands-ai/runtime:0.43-nikolaik'
    )

    # Create event stream
    file_store = get_file_store(
        config.file_store,
        config.file_store_path,
        config.file_store_web_hook_url,
        config.file_store_web_hook_headers,
    )
    event_stream = EventStream('test-nomad-runtime', file_store)

    # Create runtime
    runtime = NomadRuntime(
        config=config,
        event_stream=event_stream,
        sid='test-nomad-runtime',
        headless_mode=True,
    )

    try:
        print('Connecting to Nomad runtime...')
        await runtime.connect()
        print(f'Runtime connected! URL: {runtime.runtime_url}')

        # Test basic command execution
        print('Testing command execution...')
        action = CmdRunAction(command='echo "Hello from Nomad runtime!"')
        observation = runtime.run_action(action)
        print(f'Command result: {observation}')

        # Test Python execution
        print('Testing Python execution...')
        action = CmdRunAction(command='python -c "print(\'Python is working!\')"')
        observation = runtime.run_action(action)
        print(f'Python result: {observation}')

        # Test file operations
        print('Testing file operations...')
        action = CmdRunAction(
            command='echo "test content" > /tmp/test.txt && cat /tmp/test.txt'
        )
        observation = runtime.run_action(action)
        print(f'File operations result: {observation}')

        print('All tests passed!')

    except Exception as e:
        print(f'Test failed: {e}')
        import traceback

        traceback.print_exc()
    finally:
        print('Cleaning up...')
        runtime.close()


if __name__ == '__main__':
    asyncio.run(test_nomad_runtime())
