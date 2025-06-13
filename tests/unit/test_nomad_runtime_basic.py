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


if __name__ == '__main__':
    pytest.main([__file__])
