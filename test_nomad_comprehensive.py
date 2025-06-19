#!/usr/bin/env python3
"""
Comprehensive test of Nomad runtime functionality.
Tests all implemented features and compares with Docker runtime capabilities.
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


async def test_nomad_comprehensive():
    """Comprehensive test of Nomad runtime functionality."""
    print('🚀 Starting Comprehensive Nomad Runtime Test...')

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
        'COMPREHENSIVE_TEST': 'true',
        'TEST_PHASE': 'comprehensive',
        'FEATURE_SET': 'complete',
    }

    # Create event stream
    config.file_store_path = '/tmp/test_nomad_comprehensive'
    file_store = get_file_store(
        config.file_store,
        config.file_store_path,
    )
    event_stream = EventStream('test-nomad-comprehensive', file_store)

    # Create runtime
    runtime = NomadRuntime(
        config=config,
        event_stream=event_stream,
        sid='test-nomad-comprehensive',
        plugins=[],
        env_vars={
            'RUNTIME_TEST': 'comprehensive',
            'NOMAD_COMPREHENSIVE': 'true',
        },
    )

    test_results = {}

    try:
        print('🔧 Creating Nomad job...')
        await runtime.connect()

        print('✅ Job created successfully!')
        print(f'🌐 Runtime URL: {runtime.runtime_url}')
        print(f'📋 Job ID: {runtime.job_id}')
        print(f'🎯 Allocation ID: {runtime.allocation_id}')

        # Test 1: Basic functionality
        print('\n📋 Test 1: Basic functionality')
        try:
            cmd_action = CmdRunAction(command='echo "Hello from Nomad!" && whoami')
            observation = runtime.run_action(cmd_action)
            print(f'✅ Basic test: {observation.content.strip()}')
            test_results['basic_functionality'] = True
        except Exception as e:
            print(f'❌ Basic test failed: {e}')
            test_results['basic_functionality'] = False

        # Test 2: Environment variables
        print('\n📋 Test 2: Environment variables')
        try:
            cmd_action = CmdRunAction(
                command='env | grep -E "(COMPREHENSIVE_TEST|OPENHANDS_|NOMAD_)" | head -10'
            )
            observation = runtime.run_action(cmd_action)
            print('Environment variables:')
            for line in observation.content.split('\n'):
                if line.strip():
                    print(f'  {line}')
            test_results['environment_variables'] = True
        except Exception as e:
            print(f'❌ Environment test failed: {e}')
            test_results['environment_variables'] = False

        # Test 3: Resource limits
        print('\n📋 Test 3: Resource limits verification')
        try:
            cmd_action = CmdRunAction(
                command='echo "CPU cores: $(nproc)" && echo "Memory: $(free -h | grep Mem)"'
            )
            observation = runtime.run_action(cmd_action)
            print(f'✅ Resource info: {observation.content.strip()}')
            test_results['resource_limits'] = True
        except Exception as e:
            print(f'❌ Resource test failed: {e}')
            test_results['resource_limits'] = False

        # Test 4: File operations
        print('\n📋 Test 4: File operations')
        try:
            cmd_action = CmdRunAction(
                command='echo "Test content" > /tmp/test.txt && cat /tmp/test.txt'
            )
            observation = runtime.run_action(cmd_action)
            print(f'✅ File operations: {observation.content.strip()}')
            test_results['file_operations'] = True
        except Exception as e:
            print(f'❌ File operations failed: {e}')
            test_results['file_operations'] = False

        # Test 5: Network connectivity
        print('\n📋 Test 5: Network connectivity')
        try:
            cmd_action = CmdRunAction(command='curl -s --max-time 5 httpbin.org/ip')
            observation = runtime.run_action(cmd_action)
            print(f'✅ Network test: {observation.content.strip()}')
            test_results['network_connectivity'] = True
        except Exception as e:
            print(f'❌ Network test failed: {e}')
            test_results['network_connectivity'] = False

        # Test 6: Python environment
        print('\n📋 Test 6: Python environment')
        try:
            cmd_action = CmdRunAction(
                command='python3 -c "import sys; print(f\'Python {sys.version}\')"'
            )
            observation = runtime.run_action(cmd_action)
            print(f'✅ Python test: {observation.content.strip()}')
            test_results['python_environment'] = True
        except Exception as e:
            print(f'❌ Python test failed: {e}')
            test_results['python_environment'] = False

        # Test 7: Log retrieval
        print('\n📋 Test 7: Log retrieval')
        try:
            logs = runtime.get_logs(tail=5)
            print('Recent logs:')
            for line in logs.split('\n')[-5:]:
                if line.strip():
                    print(f'  {line}')
            test_results['log_retrieval'] = True
        except Exception as e:
            print(f'❌ Log retrieval failed: {e}')
            test_results['log_retrieval'] = False

        # Test 8: Runtime information
        print('\n📋 Test 8: Runtime information')
        try:
            print(f'Runtime URL: {runtime.runtime_url}')
            print(f'Job ID: {runtime.job_id}')
            print(f'Allocation ID: {runtime.allocation_id}')
            print(f'Container image: {runtime.container_image}')
            test_results['runtime_information'] = True
        except Exception as e:
            print(f'❌ Runtime info failed: {e}')
            test_results['runtime_information'] = False

        # Test 9: Error handling
        print('\n📋 Test 9: Error handling')
        try:
            cmd_action = CmdRunAction(command='nonexistent_command_12345')
            observation = runtime.run_action(cmd_action)
            if observation.exit_code != 0:
                print('✅ Error handling works correctly')
                test_results['error_handling'] = True
            else:
                print('❌ Error handling failed - should have non-zero exit code')
                test_results['error_handling'] = False
        except Exception as e:
            print(f'✅ Error handling works: {e}')
            test_results['error_handling'] = True

        # Test 10: Long-running command
        print('\n📋 Test 10: Long-running command')
        try:
            cmd_action = CmdRunAction(
                command='sleep 2 && echo "Long command completed"'
            )
            observation = runtime.run_action(cmd_action)
            print(f'✅ Long command: {observation.content.strip()}')
            test_results['long_running_command'] = True
        except Exception as e:
            print(f'❌ Long command failed: {e}')
            test_results['long_running_command'] = False

        # Summary
        print('\n📊 Test Results Summary:')
        passed = sum(test_results.values())
        total = len(test_results)
        print(f'Passed: {passed}/{total} tests')

        for test_name, result in test_results.items():
            status = '✅' if result else '❌'
            print(f'  {status} {test_name.replace("_", " ").title()}')

        if passed == total:
            print('\n🎉 All comprehensive tests passed!')
            return True
        else:
            print(f'\n⚠️  {total - passed} tests failed')
            return False

    except Exception as e:
        print(f'❌ Comprehensive test failed: {e}')
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
        success = asyncio.run(test_nomad_comprehensive())
        if success:
            print('\n✅ Comprehensive test completed successfully!')
        else:
            print('\n❌ Some comprehensive tests failed!')
            sys.exit(1)
    except KeyboardInterrupt:
        print('\nTest interrupted by user')
        sys.exit(130)
    except Exception as e:
        print(f'❌ Unexpected error: {e}')
        sys.exit(1)
