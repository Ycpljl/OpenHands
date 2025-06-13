"""Basic tests for Nomad runtime implementation."""

from unittest.mock import Mock, patch

import pytest

from openhands.runtime.impl.nomad.nomad_runtime import NomadRuntime


def test_nomad_runtime_import():
    """Test that NomadRuntime can be imported."""
    assert NomadRuntime is not None


def test_nomad_runtime_class_exists():
    """Test that NomadRuntime class exists and has expected methods."""
    # Check that the class exists
    assert hasattr(NomadRuntime, '__init__')
    assert hasattr(NomadRuntime, 'connect')
    assert hasattr(NomadRuntime, 'close')
    assert hasattr(NomadRuntime, 'log')
    assert hasattr(NomadRuntime, '_get_nomad_headers')
    assert hasattr(NomadRuntime, '_create_job_spec')
    assert hasattr(NomadRuntime, 'action_execution_server_url')


def test_get_nomad_headers_with_token():
    """Test Nomad headers generation with token."""
    # Create a minimal runtime instance for testing headers
    runtime = object.__new__(NomadRuntime)  # Create without calling __init__
    runtime.nomad_token = 'test-token'

    headers = runtime._get_nomad_headers()

    assert headers['Content-Type'] == 'application/json'
    assert headers['X-Nomad-Token'] == 'test-token'


def test_get_nomad_headers_without_token():
    """Test Nomad headers generation without token."""
    # Create a minimal runtime instance for testing headers
    runtime = object.__new__(NomadRuntime)  # Create without calling __init__
    runtime.nomad_token = None

    headers = runtime._get_nomad_headers()

    assert headers['Content-Type'] == 'application/json'
    assert 'X-Nomad-Token' not in headers


def test_action_execution_server_url_property():
    """Test action execution server URL property."""
    # Create a minimal runtime instance
    runtime = object.__new__(NomadRuntime)  # Create without calling __init__

    # Test when runtime_url is not set
    runtime.runtime_url = None
    with pytest.raises(NotImplementedError, match='Runtime URL is not initialized'):
        _ = runtime.action_execution_server_url

    # Test when runtime_url is set
    runtime.runtime_url = 'http://192.168.1.100:12345'
    assert runtime.action_execution_server_url == 'http://192.168.1.100:12345'


def test_log_method_with_attributes():
    """Test log method when attributes are present."""
    # Create a minimal runtime instance
    runtime = object.__new__(NomadRuntime)  # Create without calling __init__
    runtime.sid = 'test-session'
    runtime.job_id = 'test-job'
    runtime.allocation_id = 'test-alloc'

    # Mock the logger
    with patch('openhands.runtime.impl.nomad.nomad_runtime.logger') as mock_logger:
        mock_logger.info = Mock()

        runtime.log('info', 'test message')

        mock_logger.info.assert_called_once_with(
            'test message',
            stacklevel=2,
            exc_info=None,
            extra={
                'session_id': 'test-session',
                'job_id': 'test-job',
                'allocation_id': 'test-alloc',
            },
        )


def test_log_method_without_attributes():
    """Test log method when optional attributes are missing."""
    # Create a minimal runtime instance
    runtime = object.__new__(NomadRuntime)  # Create without calling __init__
    runtime.sid = 'test-session'
    # Don't set job_id and allocation_id

    # Mock the logger
    with patch('openhands.runtime.impl.nomad.nomad_runtime.logger') as mock_logger:
        mock_logger.info = Mock()

        runtime.log('info', 'test message')

        mock_logger.info.assert_called_once_with(
            'test message',
            stacklevel=2,
            exc_info=None,
            extra={'session_id': 'test-session'},
        )


def test_close_method_safe():
    """Test that close method handles missing attributes gracefully."""
    # Create a minimal runtime instance
    runtime = object.__new__(NomadRuntime)  # Create without calling __init__
    runtime._runtime_closed = False
    runtime.attach_to_existing = False
    runtime.sid = 'test-session'

    # Mock nomad_client
    runtime.nomad_client = Mock()
    runtime.nomad_client.close = Mock()

    # Mock the log method to avoid logger issues
    runtime.log = Mock()

    # This should not raise an exception even without job_id
    runtime.close()

    assert runtime._runtime_closed is True
    runtime.nomad_client.close.assert_called_once()
    runtime.log.assert_called_with('info', 'Closing Nomad runtime')


def test_gpu_job_spec_creation():
    """Test that GPU configuration is properly added to job spec."""
    from openhands.core.config import OpenHandsConfig

    config = OpenHandsConfig(
        runtime='nomad',
        sandbox={
            'enable_gpu': True,
            'nomad_gpu_count': 2,
            'nomad_gpu_type': 'nvidia/tesla-v100',
            'runtime_container_image': 'test-image:latest',
        },
    )

    runtime = NomadRuntime(config=config, event_stream=None, sid='test-session')
    job_spec = runtime._create_job_spec()

    # Check that GPU devices are added
    task_groups = job_spec.get('TaskGroups', [])
    assert len(task_groups) > 0

    tasks = task_groups[0].get('Tasks', [])
    assert len(tasks) > 0

    task = tasks[0]
    resources = task.get('Resources', {})
    devices = resources.get('Devices', [])

    # Should have GPU device configuration
    assert len(devices) > 0
    gpu_device = devices[0]
    assert gpu_device['Name'] == 'nvidia/tesla-v100'
    assert gpu_device['Count'] == 2

    # Check Docker configuration for GPU
    docker_config = task.get('Config', {})
    assert docker_config.get('runtime') == 'nvidia'
    assert 'cap_add' in docker_config
    assert 'SYS_ADMIN' in docker_config['cap_add']
    assert 'devices' in docker_config

    # Check GPU environment variables
    env = task.get('Env', {})
    assert env.get('NVIDIA_VISIBLE_DEVICES') == 'all'
    assert env.get('NVIDIA_DRIVER_CAPABILITIES') == 'compute,utility'
    assert env.get('CUDA_VISIBLE_DEVICES') == 'all'

    # Check constraints for NVIDIA runtime
    constraints = task.get('Constraints', [])
    nvidia_constraint = next(
        (
            c
            for c in constraints
            if c.get('LTarget') == '${attr.driver.docker.runtime.nvidia}'
        ),
        None,
    )
    assert nvidia_constraint is not None
    assert nvidia_constraint['RTarget'] == 'true'
    assert nvidia_constraint['Operand'] == '='


def test_gpu_job_spec_defaults():
    """Test that GPU configuration uses proper defaults."""
    from openhands.core.config import OpenHandsConfig

    config = OpenHandsConfig(
        runtime='nomad',
        sandbox={'enable_gpu': True, 'runtime_container_image': 'test-image:latest'},
    )
    # Don't set gpu_count or gpu_type to test defaults

    runtime = NomadRuntime(config=config, event_stream=None, sid='test-session')
    job_spec = runtime._create_job_spec()

    # Check that default GPU configuration is used
    task_groups = job_spec.get('TaskGroups', [])
    tasks = task_groups[0].get('Tasks', [])
    task = tasks[0]
    resources = task.get('Resources', {})
    devices = resources.get('Devices', [])

    # Should use defaults
    gpu_device = devices[0]
    assert gpu_device['Name'] == 'nvidia/gpu'  # Default GPU type
    assert gpu_device['Count'] == 1  # Default GPU count


def test_no_gpu_job_spec():
    """Test that GPU configuration is not added when GPU is disabled."""
    from openhands.core.config import OpenHandsConfig

    config = OpenHandsConfig(
        runtime='nomad',
        sandbox={'enable_gpu': False, 'runtime_container_image': 'test-image:latest'},
    )

    runtime = NomadRuntime(config=config, event_stream=None, sid='test-session')
    job_spec = runtime._create_job_spec()

    # Check that no GPU devices are added
    task_groups = job_spec.get('TaskGroups', [])
    tasks = task_groups[0].get('Tasks', [])
    task = tasks[0]
    resources = task.get('Resources', {})
    devices = resources.get('Devices')

    # Should not have GPU devices
    assert devices is None

    # Should not have GPU-specific Docker config
    docker_config = task.get('Config', {})
    assert docker_config.get('runtime') != 'nvidia'


if __name__ == '__main__':
    pytest.main([__file__])
