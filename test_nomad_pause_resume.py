#!/usr/bin/env python3
"""
Test pause/resume functionality of Nomad runtime.
"""

import asyncio
import logging
import signal
import sys

from openhands.core.config import OpenHandsConfig
from openhands.events.action import CmdRunAction
from openhands.events.stream import EventStream
from openhands.runtime.impl.nomad.nomad_runtime import NomadRuntime
from openhands.storage import get_file_store

# Configure logging
logging.basicConfig(level=logging.INFO)


async def test_nomad_pause_resume():
    """Test pause/resume functionality of Nomad runtime."""
    print('🚀 Starting Nomad Runtime Pause/Resume Test...')

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

    # Configure IP mapping
    config.sandbox.nomad_ip_mapping = {
        '192.168.0.133': '119.8.51.245',
    }

    # Create event stream
    config.file_store_path = '/tmp/test_nomad_pause_resume'
    file_store = get_file_store(
        config.file_store,
        config.file_store_path,
    )
    event_stream = EventStream('test-nomad-pause-resume', file_store)

    # Create runtime
    runtime = NomadRuntime(
        config=config,
        event_stream=event_stream,
        sid='test-nomad-pause-resume',
        plugins=[],
        env_vars={
            'PAUSE_RESUME_TEST': 'true',
        },
    )

    try:
        print('🔧 Creating Nomad job...')
        await runtime.connect()

        print('✅ Job created successfully!')
        print(f'🌐 Runtime URL: {runtime.runtime_url}')
        print(f'📋 Job ID: {runtime.job_id}')
        print(f'🎯 Allocation ID: {runtime.allocation_id}')

        # Test 1: Verify runtime is working
        print('\n📋 Test 1: Verify runtime is working')
        cmd_action = CmdRunAction(command='echo "Runtime is working!" && date')
        observation = runtime.run_action(cmd_action)
        print(f'Initial test: {observation.content}')

        # Test 2: Pause the runtime
        print('\n📋 Test 2: Pausing runtime...')
        runtime.pause()
        print('✅ Runtime paused successfully')

        # Wait a moment
        await asyncio.sleep(3)

        # Test 3: Try to use runtime while paused (should fail or timeout)
        print('\n📋 Test 3: Testing runtime while paused (should fail)...')
        try:
            cmd_action = CmdRunAction(command='echo "This should not work"')
            observation = runtime.run_action(cmd_action)
            print(f'❌ Unexpected success while paused: {observation.content}')
        except Exception as e:
            print(f'✅ Expected failure while paused: {e}')

        # Test 4: Resume the runtime
        print('\n📋 Test 4: Resuming runtime...')
        runtime.resume()
        print('✅ Runtime resumed successfully')

        # Wait for runtime to be ready again
        print('⏳ Waiting for runtime to be ready...')
        await asyncio.sleep(10)

        # Test 5: Verify runtime is working again
        print('\n📋 Test 5: Verify runtime is working after resume')
        cmd_action = CmdRunAction(command='echo "Runtime is working again!" && date')
        observation = runtime.run_action(cmd_action)
        print(f'Resume test: {observation.content}')

        print('\n🎉 Pause/Resume test completed successfully!')
        return True

    except Exception as e:
        print(f'❌ Pause/Resume test failed: {e}')
        import traceback

        traceback.print_exc()
        return False
    finally:
        print('\n🧹 Cleaning up...')
        try:
            runtime.close()
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
        success = asyncio.run(test_nomad_pause_resume())
        if success:
            print('\n✅ Pause/Resume test completed successfully!')
        else:
            print('\n❌ Pause/Resume test failed!')
            sys.exit(1)
    except KeyboardInterrupt:
        print('\nTest interrupted by user')
        sys.exit(130)
    except Exception as e:
        print(f'❌ Unexpected error: {e}')
        sys.exit(1)
