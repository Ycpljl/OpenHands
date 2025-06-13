"""Tests for Nomad runtime implementation."""

from unittest.mock import Mock, patch

import httpx
import pytest

from openhands.core.config import OpenHandsConfig
from openhands.core.exceptions import (
    AgentRuntimeError,
    AgentRuntimeUnavailableError,
)
from openhands.events import EventStream
from openhands.runtime.impl.nomad.nomad_runtime import NomadRuntime


@pytest.fixture
def mock_config():
    """Create a mock OpenHandsConfig for testing."""
    config = Mock(spec=OpenHandsConfig)
    config.sandbox = Mock()
    config.sandbox.nomad_address = 'http://localhost:4646'
    config.sandbox.nomad_token = 'test-token'
    config.sandbox.nomad_namespace = 'test'
    config.sandbox.nomad_datacenter = 'dc1'
    config.sandbox.nomad_cpu = 1000
    config.sandbox.nomad_memory = 2048
    config.sandbox.runtime_container_image = 'test-image:latest'
    config.sandbox.base_container_image = None
    config.sandbox.enable_gpu = False
    config.sandbox.runtime_startup_env_vars = {}
    config.debug = False
    return config


@pytest.fixture
def mock_event_stream():
    """Create a mock EventStream for testing."""
    return Mock(spec=EventStream)


@pytest.fixture
def nomad_runtime(mock_config, mock_event_stream):
    """Create a NomadRuntime instance for testing."""
    with patch('httpx.Client'):
        runtime = NomadRuntime(
            config=mock_config, event_stream=mock_event_stream, sid='test-session'
        )
        return runtime


class TestNomadRuntime:
    """Test cases for NomadRuntime."""

    def test_init_with_config(self, mock_config, mock_event_stream):
        """Test NomadRuntime initialization with configuration."""
        with patch('httpx.Client') as mock_client:
            runtime = NomadRuntime(
                config=mock_config, event_stream=mock_event_stream, sid='test-session'
            )

            assert runtime.nomad_address == 'http://localhost:4646'
            assert runtime.nomad_token == 'test-token'
            assert runtime.nomad_namespace == 'test'
            assert runtime.nomad_datacenter == 'dc1'
            assert runtime.job_id == 'openhands-runtime-test-session'
            assert runtime.container_image == 'test-image:latest'

            # Verify HTTP client was created with correct parameters
            mock_client.assert_called_once_with(
                base_url='http://localhost:4646',
                headers={
                    'Content-Type': 'application/json',
                    'X-Nomad-Token': 'test-token',
                },
                timeout=30.0,
            )

    def test_init_with_env_vars(self, mock_event_stream):
        """Test NomadRuntime initialization with environment variables."""
        config = Mock(spec=OpenHandsConfig)
        config.sandbox = Mock()
        config.sandbox.nomad_address = None
        config.sandbox.nomad_token = None
        config.sandbox.nomad_namespace = None
        config.sandbox.nomad_datacenter = None
        config.sandbox.runtime_container_image = 'test-image:latest'
        config.sandbox.runtime_startup_env_vars = {}
        config.debug = False

        with patch.dict(
            'os.environ',
            {
                'NOMAD_ADDR': 'http://env-nomad:4646',
                'NOMAD_TOKEN': 'env-token',
                'NOMAD_NAMESPACE': 'env-namespace',
                'NOMAD_DATACENTER': 'env-dc',
            },
        ):
            with patch('httpx.Client'):
                runtime = NomadRuntime(
                    config=config, event_stream=mock_event_stream, sid='test-session'
                )

                assert runtime.nomad_address == 'http://env-nomad:4646'
                assert runtime.nomad_token == 'env-token'
                assert runtime.nomad_namespace == 'env-namespace'
                assert runtime.nomad_datacenter == 'env-dc'

    def test_init_missing_container_image(self, mock_event_stream):
        """Test NomadRuntime initialization fails without container image."""
        config = Mock(spec=OpenHandsConfig)
        config.sandbox = Mock()
        config.sandbox.nomad_address = 'http://localhost:4646'
        config.sandbox.runtime_container_image = None
        config.sandbox.base_container_image = None

        with pytest.raises(ValueError, match='Container image is required'):
            NomadRuntime(
                config=config, event_stream=mock_event_stream, sid='test-session'
            )

    def test_create_job_spec(self, nomad_runtime):
        """Test job specification creation."""
        with patch.object(
            nomad_runtime, 'get_action_execution_server_startup_command'
        ) as mock_cmd:
            mock_cmd.return_value = [
                '/usr/bin/python',
                '-m',
                'openhands.runtime.action_execution_server',
            ]

            job_spec = nomad_runtime._create_job_spec()

            assert job_spec['ID'] == 'openhands-runtime-test-session'
            assert job_spec['Name'] == 'openhands-runtime-test-session'
            assert job_spec['Type'] == 'service'
            assert job_spec['Datacenters'] == ['dc1']
            assert job_spec['Namespace'] == 'test'

            task_group = job_spec['TaskGroups'][0]
            assert task_group['Name'] == 'runtime'
            assert task_group['Count'] == 1

            task = task_group['Tasks'][0]
            assert task['Name'] == 'action-server'
            assert task['Driver'] == 'docker'
            assert task['Config']['image'] == 'test-image:latest'
            assert task['Config']['command'] == '/usr/bin/python'
            assert task['Config']['args'] == [
                '-m',
                'openhands.runtime.action_execution_server',
            ]
            assert task['Config']['work_dir'] == '/openhands/code/'

            resources = task['Resources']
            assert resources['CPU'] == 1000
            assert resources['MemoryMB'] == 2048

    def test_create_job_spec_with_gpu(self, nomad_runtime):
        """Test job specification creation with GPU support."""
        nomad_runtime.config.sandbox.enable_gpu = True

        with patch.object(
            nomad_runtime, 'get_action_execution_server_startup_command'
        ) as mock_cmd:
            mock_cmd.return_value = [
                '/usr/bin/python',
                '-m',
                'openhands.runtime.action_execution_server',
            ]

            job_spec = nomad_runtime._create_job_spec()

            task = job_spec['TaskGroups'][0]['Tasks'][0]
            devices = task['Resources']['Devices']
            assert len(devices) == 1
            assert devices[0]['Name'] == 'nvidia/gpu'
            assert devices[0]['Count'] == 1

    def test_check_existing_job_found(self, nomad_runtime):
        """Test checking for existing job when job exists."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'Status': 'running'}

        nomad_runtime.nomad_client.get.return_value = mock_response

        result = nomad_runtime._check_existing_job()

        assert result is True
        nomad_runtime.nomad_client.get.assert_called_once_with(
            '/v1/job/openhands-runtime-test-session'
        )

    def test_check_existing_job_not_found(self, nomad_runtime):
        """Test checking for existing job when job doesn't exist."""
        mock_response = Mock()
        mock_response.status_code = 404

        nomad_runtime.nomad_client.get.return_value = mock_response

        result = nomad_runtime._check_existing_job()

        assert result is False

    def test_check_existing_job_stopped(self, nomad_runtime):
        """Test checking for existing job when job is stopped."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'Status': 'dead'}

        nomad_runtime.nomad_client.get.return_value = mock_response

        result = nomad_runtime._check_existing_job()

        assert result is False

    def test_start_job_success(self, nomad_runtime):
        """Test successful job start."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'EvalID': 'eval-123'}

        nomad_runtime.nomad_client.post.return_value = mock_response

        with patch.object(nomad_runtime, '_create_job_spec') as mock_spec:
            mock_spec.return_value = {'ID': 'test-job'}
            with patch.object(nomad_runtime, '_wait_for_allocation'):
                nomad_runtime._start_job()

                nomad_runtime.nomad_client.post.assert_called_once_with(
                    '/v1/jobs', json={'Job': {'ID': 'test-job'}}
                )

    def test_start_job_failure(self, nomad_runtime):
        """Test job start failure."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Bad request'

        error = httpx.HTTPStatusError(
            'Bad request', request=Mock(), response=mock_response
        )
        nomad_runtime.nomad_client.post.side_effect = error

        with patch.object(nomad_runtime, '_create_job_spec') as mock_spec:
            mock_spec.return_value = {'ID': 'test-job'}

            with pytest.raises(AgentRuntimeUnavailableError):
                nomad_runtime._start_job()

    def test_wait_for_allocation_success(self, nomad_runtime):
        """Test successful allocation wait."""
        # First call returns empty allocations, second call returns running allocation
        mock_responses = [
            Mock(status_code=200, json=lambda: []),
            Mock(
                status_code=200,
                json=lambda: [{'ID': 'alloc-123', 'ClientStatus': 'running'}],
            ),
        ]

        nomad_runtime.nomad_client.get.side_effect = mock_responses

        with patch.object(
            nomad_runtime, '_get_allocation_network_info'
        ) as mock_network:
            with patch('time.sleep'):  # Mock sleep to speed up test
                nomad_runtime._wait_for_allocation()

                assert nomad_runtime.allocation_id == 'alloc-123'
                mock_network.assert_called_once()

    def test_wait_for_allocation_failed(self, nomad_runtime):
        """Test allocation wait with failed allocation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'ID': 'alloc-123', 'ClientStatus': 'failed'}
        ]

        nomad_runtime.nomad_client.get.return_value = mock_response

        with pytest.raises(AgentRuntimeError, match='Allocation failed'):
            nomad_runtime._wait_for_allocation()

    def test_wait_for_allocation_timeout(self, nomad_runtime):
        """Test allocation wait timeout."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []  # Always return empty allocations

        nomad_runtime.nomad_client.get.return_value = mock_response

        with patch('time.sleep'):  # Mock sleep to speed up test
            with pytest.raises(AgentRuntimeError, match='Timeout waiting'):
                nomad_runtime._wait_for_allocation()

    def test_get_allocation_network_info(self, nomad_runtime):
        """Test extracting network info from allocation."""
        allocation = {'ID': 'alloc-123'}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'Resources': {
                'Networks': [
                    {
                        'IP': '192.168.1.100',
                        'DynamicPorts': [{'Label': 'action_server', 'Value': 12345}],
                    }
                ]
            }
        }

        nomad_runtime.nomad_client.get.return_value = mock_response

        nomad_runtime._get_allocation_network_info(allocation)

        assert nomad_runtime.runtime_url == 'http://192.168.1.100:12345'
        nomad_runtime.nomad_client.get.assert_called_once_with(
            '/v1/allocation/alloc-123'
        )

    def test_get_allocation_network_info_no_port(self, nomad_runtime):
        """Test network info extraction when action server port is missing."""
        allocation = {'ID': 'alloc-123'}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'Resources': {
                'Networks': [
                    {
                        'IP': '192.168.1.100',
                        'DynamicPorts': [{'Label': 'other_port', 'Value': 12345}],
                    }
                ]
            }
        }

        nomad_runtime.nomad_client.get.return_value = mock_response

        with pytest.raises(AgentRuntimeError, match='Action server port not found'):
            nomad_runtime._get_allocation_network_info(allocation)

    def test_close_runtime(self, nomad_runtime):
        """Test runtime cleanup."""
        nomad_runtime.job_id = 'test-job'
        nomad_runtime._runtime_closed = False

        mock_response = Mock()
        mock_response.status_code = 200
        nomad_runtime.nomad_client.delete.return_value = mock_response

        nomad_runtime.close()

        assert nomad_runtime._runtime_closed is True
        nomad_runtime.nomad_client.delete.assert_called_once_with('/v1/job/test-job')
        nomad_runtime.nomad_client.close.assert_called_once()

    def test_close_runtime_attach_mode(self, nomad_runtime):
        """Test runtime cleanup in attach mode (should not delete job)."""
        nomad_runtime.attach_to_existing = True
        nomad_runtime._runtime_closed = False

        nomad_runtime.close()

        assert nomad_runtime._runtime_closed is True
        nomad_runtime.nomad_client.delete.assert_not_called()
        nomad_runtime.nomad_client.close.assert_called_once()

    def test_action_execution_server_url_not_initialized(self, nomad_runtime):
        """Test action execution server URL when not initialized."""
        nomad_runtime.runtime_url = None

        with pytest.raises(NotImplementedError, match='Runtime URL is not initialized'):
            _ = nomad_runtime.action_execution_server_url

    def test_action_execution_server_url_initialized(self, nomad_runtime):
        """Test action execution server URL when initialized."""
        nomad_runtime.runtime_url = 'http://192.168.1.100:12345'

        assert nomad_runtime.action_execution_server_url == 'http://192.168.1.100:12345'

    @pytest.mark.asyncio
    async def test_connect_new_job(self, nomad_runtime):
        """Test connecting with new job creation."""
        nomad_runtime.attach_to_existing = False

        with patch.object(nomad_runtime, '_start_or_attach_to_job') as mock_start:
            with patch.object(nomad_runtime, 'setup_initial_env') as mock_setup:
                await nomad_runtime.connect()

                mock_start.assert_called_once()
                mock_setup.assert_called_once()
                assert nomad_runtime._runtime_initialized is True

    @pytest.mark.asyncio
    async def test_connect_attach_existing(self, nomad_runtime):
        """Test connecting by attaching to existing job."""
        nomad_runtime.attach_to_existing = True

        with patch.object(nomad_runtime, '_start_or_attach_to_job') as mock_start:
            with patch.object(nomad_runtime, 'setup_initial_env') as mock_setup:
                await nomad_runtime.connect()

                mock_start.assert_called_once()
                mock_setup.assert_called_once()
                assert nomad_runtime._runtime_initialized is True

    @pytest.mark.asyncio
    async def test_connect_failure(self, nomad_runtime):
        """Test connection failure handling."""
        with patch.object(nomad_runtime, '_start_or_attach_to_job') as mock_start:
            with patch.object(nomad_runtime, 'close') as mock_close:
                mock_start.side_effect = Exception('Connection failed')

                with pytest.raises(Exception, match='Connection failed'):
                    await nomad_runtime.connect()

                mock_close.assert_called_once()
