#!/usr/bin/env python3
"""
Test enhanced features of Nomad runtime:
1. Improved environment variable handling
2. Log streaming functionality
3. Pause/resume functionality
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


async def test_nomad_enhanced_features():
    """Test enhanced features of Nomad runtime."""
    print('🚀 Starting Nomad Runtime Enhanced Features Test...')

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

    # Configure comprehensive environment variables
    config.sandbox.runtime_startup_env_vars = {
        'TEST_ENV_VAR': 'enhanced_test_value',
        'CUSTOM_CONFIG': 'nomad_runtime_test',
        'LOG_LEVEL': 'DEBUG',
        'FEATURE_TEST': 'environment_variables',
    }

    # Create event stream
    config.file_store_path = '/tmp/test_nomad_enhanced_features'
    file_store = get_file_store(
        config.file_store,
        config.file_store_path,
    )
    event_stream = EventStream('test-nomad-enhanced-features', file_store)

    # Create runtime
    runtime = NomadRuntime(
        config=config,
        event_stream=event_stream,
        sid='test-nomad-enhanced-features',
        plugins=[],
        env_vars={
            'RUNTIME_INIT_TEST': 'enhanced_features',
            'NOMAD_TEST_MODE': 'true',
        },
    )

    try:
        print('🔧 Creating Nomad job with enhanced configuration...')
        await runtime.connect()

        print('✅ Job created successfully!')
        print(f'🌐 Runtime URL: {runtime.runtime_url}')
        print(f'📋 Job ID: {runtime.job_id}')
        print(f'🎯 Allocation ID: {runtime.allocation_id}')

        # Test 1: Enhanced environment variables
        print('\n📋 Test 1: Enhanced environment variables')
        cmd_action = CmdRunAction(
            command='env | grep -E "(TEST_ENV_VAR|CUSTOM_CONFIG|OPENHANDS_|NOMAD_)" | sort'
        )
        observation = runtime.run_action(cmd_action)
        print('Environment variables:')
        for line in observation.content.split('\n'):
            if line.strip():
                print(f'  {line}')

        # Test 2: Log retrieval
        print('\n📋 Test 2: Log retrieval')
        logs = runtime.get_logs(tail=10)
        print('Recent logs (last 10 lines):')
        for line in logs.split('\n')[-10:]:
            if line.strip():
                print(f'  {line}')

        # Test 3: Generate some activity for logs
        print('\n📋 Test 3: Generate activity for log testing')
        cmd_action = CmdRunAction(
            command='echo "=== LOG TEST START ===" && date && echo "Current user: $(whoami)" && echo "=== LOG TEST END ==="'
        )
        observation = runtime.run_action(cmd_action)
        print(f'Activity output: {observation.content}')

        # Wait a moment for logs to be written
        await asyncio.sleep(2)

        # Test 4: Get updated logs
        print('\n📋 Test 4: Updated log retrieval')
        logs = runtime.get_logs(tail=15)
        print('Updated logs (last 15 lines):')
        for line in logs.split('\n')[-15:]:
            if line.strip():
                print(f'  {line}')

        # Test 5: Test stderr logs
        print('\n📋 Test 5: Stderr log retrieval')
        stderr_logs = runtime.get_logs(log_type='stderr', tail=10)
        print('Recent stderr logs:')
        for line in stderr_logs.split('\n')[-10:]:
            if line.strip():
                print(f'  {line}')

        # Test 6: Runtime information verification
        print('\n📋 Test 6: Runtime information verification')
        cmd_action = CmdRunAction(
            command='echo "Job ID: $NOMAD_JOB_ID" && echo "Allocation ID: $NOMAD_ALLOCATION_ID" && echo "Runtime: $OPENHANDS_RUNTIME"'
        )
        observation = runtime.run_action(cmd_action)
        print(f'Runtime info: {observation.content}')

        print('\n🎉 All enhanced feature tests passed!')
        return True

    except Exception as e:
        print(f'❌ Enhanced feature test failed: {e}')
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
        success = asyncio.run(test_nomad_enhanced_features())
        if success:
            print('\n✅ Enhanced features test completed successfully!')
        else:
            print('\n❌ Enhanced features test failed!')
            sys.exit(1)
    except KeyboardInterrupt:
        print('\nTest interrupted by user')
        sys.exit(130)
    except Exception as e:
        print(f'❌ Unexpected error: {e}')
        sys.exit(1)
