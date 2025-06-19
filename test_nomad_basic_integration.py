#!/usr/bin/env python3
"""
Basic integration test for Nomad runtime without volume mounts.
Tests core functionality that doesn't require host filesystem access.
"""

import asyncio
import logging
import signal
import sys

from openhands.core.config import OpenHandsConfig
from openhands.events.action import CmdRunAction, FileReadAction, FileWriteAction
from openhands.events.stream import EventStream
from openhands.runtime.impl.nomad.nomad_runtime import NomadRuntime
from openhands.storage import get_file_store

# Configure logging
logging.basicConfig(level=logging.INFO)


async def test_nomad_basic_integration():
    """Basic integration test for Nomad runtime."""
    print('🚀 Starting Nomad Runtime Basic Integration Test...')

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

    # Configure environment variables
    config.sandbox.runtime_startup_env_vars = {
        'TEST_ENV_VAR': 'test_value',
        'INTEGRATION_TEST': 'nomad_basic',
    }

    # Create event stream
    config.file_store_path = '/tmp/test_nomad_basic_integration'
    file_store = get_file_store(
        config.file_store,
        config.file_store_path,
    )
    event_stream = EventStream('test-nomad-basic-integration', file_store)

    # Create runtime
    runtime = NomadRuntime(
        config=config,
        event_stream=event_stream,
        sid='test-nomad-basic-integration',
        plugins=[],
        env_vars={'RUNTIME_TEST': 'basic'},
    )

    try:
        print('🔧 Creating Nomad job...')
        await runtime.connect()

        print('✅ Job created successfully!')
        print(f'🌐 Runtime URL: {runtime.runtime_url}')

        # Test 1: Basic command execution
        print('\n📋 Test 1: Basic command execution')
        cmd_action = CmdRunAction(command='echo "Hello from Nomad runtime!"')
        observation = runtime.run_action(cmd_action)
        print(f'Command output: {observation.content}')
        assert 'Hello from Nomad runtime!' in observation.content

        # Test 2: Environment variable access
        print('\n📋 Test 2: Environment variable access')
        cmd_action = CmdRunAction(command='echo "Test env: $TEST_ENV_VAR"')
        observation = runtime.run_action(cmd_action)
        print(f'Environment output: {observation.content}')
        assert 'test_value' in observation.content

        # Test 3: Runtime environment variable
        print('\n📋 Test 3: Runtime environment variable')
        cmd_action = CmdRunAction(command='echo "Runtime test: $RUNTIME_TEST"')
        observation = runtime.run_action(cmd_action)
        print(f'Runtime env output: {observation.content}')
        assert 'basic' in observation.content

        # Test 4: Python execution
        print('\n📋 Test 4: Python execution')
        cmd_action = CmdRunAction(
            command='python3 -c "import sys; print(f\'Python version: {sys.version}\')"'
        )
        observation = runtime.run_action(cmd_action)
        print(f'Python output: {observation.content}')
        assert 'Python version:' in observation.content

        # Test 5: Working directory
        print('\n📋 Test 5: Working directory verification')
        cmd_action = CmdRunAction(command='pwd')
        observation = runtime.run_action(cmd_action)
        print(f'Working directory: {observation.content}')
        # The working directory should be either /workspace or /openhands/code
        assert (
            '/workspace' in observation.content
            or '/openhands/code' in observation.content
        )

        # Test 6: File operations in container
        print('\n📋 Test 6: File operations in container')
        write_action = FileWriteAction(
            path='/tmp/test_file.txt', content='Hello from Nomad container!'
        )
        observation = runtime.run_action(write_action)
        print(f'Write result: {observation.content}')

        # Read the file back
        read_action = FileReadAction(path='/tmp/test_file.txt')
        observation = runtime.run_action(read_action)
        print(f'Read result: {observation.content}')
        assert 'Hello from Nomad container!' in observation.content

        # Test 7: System information
        print('\n📋 Test 7: System information')
        cmd_action = CmdRunAction(command='uname -a')
        observation = runtime.run_action(cmd_action)
        print(f'System info: {observation.content}')
        assert 'Linux' in observation.content

        # Test 8: Available tools
        print('\n📋 Test 8: Available tools')
        cmd_action = CmdRunAction(command='which python3 && which pip && which git')
        observation = runtime.run_action(cmd_action)
        print(f'Available tools: {observation.content}')
        assert '/python3' in observation.content

        # Test 9: Network connectivity
        print('\n📋 Test 9: Network connectivity')
        cmd_action = CmdRunAction(
            command='curl -s --connect-timeout 5 https://httpbin.org/ip || echo "Network test skipped"'
        )
        observation = runtime.run_action(cmd_action)
        print(f'Network test: {observation.content}')

        # Test 10: Container resource limits
        print('\n📋 Test 10: Container resource information')
        cmd_action = CmdRunAction(command='cat /proc/meminfo | grep MemTotal')
        observation = runtime.run_action(cmd_action)
        print(f'Memory info: {observation.content}')

        print('\n🎉 All basic integration tests passed!')
        return True

    except Exception as e:
        print(f'❌ Integration test failed: {e}')
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
        success = asyncio.run(test_nomad_basic_integration())
        if success:
            print('\n✅ Basic integration test completed successfully!')
        else:
            print('\n❌ Basic integration test failed!')
            sys.exit(1)
    except KeyboardInterrupt:
        print('\nTest interrupted by user')
        sys.exit(130)
    except Exception as e:
        print(f'❌ Unexpected error: {e}')
        sys.exit(1)
