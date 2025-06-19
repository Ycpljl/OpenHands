#!/usr/bin/env python3
"""
Complete integration test for Nomad runtime.
Tests all major functionality including volume mounts, environment variables, and lifecycle management.
"""

import asyncio
import logging
import signal
import sys
import tempfile
from pathlib import Path

from openhands.core.config import OpenHandsConfig
from openhands.events.action import CmdRunAction, FileWriteAction
from openhands.events.stream import EventStream
from openhands.runtime.impl.nomad.nomad_runtime import NomadRuntime
from openhands.storage import get_file_store

# Configure logging
logging.basicConfig(level=logging.INFO)


async def test_nomad_integration():
    """Complete integration test for Nomad runtime."""
    print('🚀 Starting Nomad Runtime Integration Test...')

    # Create temporary workspace for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace_path = Path(temp_dir) / 'workspace'
        workspace_path.mkdir()

        # Create a test file in workspace
        test_file = workspace_path / 'test.txt'
        test_file.write_text('Hello from host filesystem!')

        print(f'📁 Created test workspace: {workspace_path}')

        # Configure OpenHands for Nomad runtime with volume mounting
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

        # Configure volume mounting
        config.sandbox.volumes = f'{workspace_path}:/workspace:rw'

        # Configure environment variables
        config.sandbox.runtime_startup_env_vars = {
            'TEST_ENV_VAR': 'test_value',
            'WORKSPACE_PATH': '/workspace',
        }

        # Create event stream
        config.file_store_path = '/tmp/test_nomad_integration'
        file_store = get_file_store(
            config.file_store,
            config.file_store_path,
        )
        event_stream = EventStream('test-nomad-integration', file_store)

        # Create runtime
        runtime = NomadRuntime(
            config=config,
            event_stream=event_stream,
            sid='test-nomad-integration',
            plugins=[],
            env_vars={'INTEGRATION_TEST': 'true'},
        )

        try:
            print('🔧 Creating Nomad job with full configuration...')
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

            # Test 3: Volume mount verification
            print('\n📋 Test 3: Volume mount verification')
            cmd_action = CmdRunAction(command='ls -la /workspace/')
            observation = runtime.run_action(cmd_action)
            print(f'Workspace listing: {observation.content}')
            assert 'test.txt' in observation.content

            # Test 4: File read from mounted volume
            print('\n📋 Test 4: File read from mounted volume')
            cmd_action = CmdRunAction(command='cat /workspace/test.txt')
            observation = runtime.run_action(cmd_action)
            print(f'File content: {observation.content}')
            assert 'Hello from host filesystem!' in observation.content

            # Test 5: File write to mounted volume
            print('\n📋 Test 5: File write to mounted volume')
            write_action = FileWriteAction(
                path='/workspace/runtime_test.txt', content='Hello from Nomad runtime!'
            )
            observation = runtime.run_action(write_action)
            print(f'Write result: {observation.content}')

            # Verify file was written on host
            runtime_test_file = workspace_path / 'runtime_test.txt'
            assert runtime_test_file.exists()
            assert runtime_test_file.read_text() == 'Hello from Nomad runtime!'
            print('✅ File successfully written to host filesystem')

            # Test 6: Python execution
            print('\n📋 Test 6: Python execution')
            cmd_action = CmdRunAction(
                command='python3 -c "import sys; print(f\'Python version: {sys.version}\')"'
            )
            observation = runtime.run_action(cmd_action)
            print(f'Python output: {observation.content}')
            assert 'Python version:' in observation.content

            # Test 7: Working directory
            print('\n📋 Test 7: Working directory verification')
            cmd_action = CmdRunAction(command='pwd')
            observation = runtime.run_action(cmd_action)
            print(f'Working directory: {observation.content}')
            assert '/openhands/code' in observation.content

            print('\n🎉 All integration tests passed!')
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
        success = asyncio.run(test_nomad_integration())
        if success:
            print('\n✅ Integration test completed successfully!')
        else:
            print('\n❌ Integration test failed!')
            sys.exit(1)
    except KeyboardInterrupt:
        print('\nTest interrupted by user')
        sys.exit(130)
    except Exception as e:
        print(f'❌ Unexpected error: {e}')
        sys.exit(1)
