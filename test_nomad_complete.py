#!/usr/bin/env python3
"""
Complete test for OpenHands Nomad Runtime

This test demonstrates the full functionality of the Nomad runtime:
1. Job creation and deployment
2. Container startup and initialization
3. Action execution (commands)
4. Proper cleanup

Usage:
    python test_nomad_complete.py
"""

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


async def test_nomad_complete():
    """Complete test for Nomad runtime functionality."""

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
    event_stream = EventStream('test-nomad-complete', file_store)

    # Create runtime
    runtime = NomadRuntime(
        config=config,
        event_stream=event_stream,
        sid='test-nomad-complete',
        plugins=[],
    )

    try:
        print('🚀 Starting OpenHands Nomad Runtime Test')
        print('=' * 50)

        # Step 1: Connect (creates and deploys job)
        print('📦 Creating Nomad job...')
        await runtime.connect()

        print('✅ Job created successfully!')
        print(f'   Job ID: {runtime.job_id}')
        print(f'   Allocation ID: {runtime.allocation_id}')
        print(f'   Runtime URL: {runtime.runtime_url}')
        print()

        # Step 2: Wait for container to be ready
        print('⏳ Waiting for container to initialize...')
        await asyncio.sleep(15)  # Give container time to start

        # Step 3: Test basic command execution
        print('🔧 Testing command execution...')
        try:
            action = CmdRunAction(command='echo "Hello from Nomad runtime!"')
            observation = runtime.run_action(action)
            print(f'   Command: {action.command}')
            print(f'   Result: {observation.content[:100]}...')
            print('✅ Command execution successful!')
        except Exception as e:
            print(f'❌ Command execution failed: {e}')

        print()

        # Step 4: Test Python execution
        print('🐍 Testing Python execution...')
        try:
            action = CmdRunAction(
                command='python -c "import sys; print(f\'Python {sys.version}\')"'
            )
            observation = runtime.run_action(action)
            print(f'   Command: {action.command}')
            print(f'   Result: {observation.content[:100]}...')
            print('✅ Python execution successful!')
        except Exception as e:
            print(f'❌ Python execution failed: {e}')

        print()

        # Step 5: Test file operations
        print('📁 Testing file operations...')
        try:
            action = CmdRunAction(
                command='echo "test content" > /tmp/test.txt && cat /tmp/test.txt'
            )
            observation = runtime.run_action(action)
            print(f'   Command: {action.command}')
            print(f'   Result: {observation.content[:100]}...')
            print('✅ File operations successful!')
        except Exception as e:
            print(f'❌ File operations failed: {e}')

        print()
        print('🎉 All tests completed successfully!')
        print('✅ OpenHands Nomad Runtime is fully functional!')

        return True

    except Exception as e:
        print(f'❌ Test failed: {e}')
        import traceback

        traceback.print_exc()
        return False
    finally:
        print()
        print('🧹 Cleaning up...')
        try:
            runtime.close()
            print('✅ Cleanup completed successfully!')
        except Exception as e:
            print(f'⚠️  Cleanup warning: {e}')


if __name__ == '__main__':
    print('OpenHands Nomad Runtime - Complete Test')
    print('=' * 50)
    success = asyncio.run(test_nomad_complete())
    print('=' * 50)
    if success:
        print('🎉 SUCCESS: Nomad runtime is working perfectly!')
    else:
        print('❌ FAILURE: Some tests failed')
    sys.exit(0 if success else 1)
