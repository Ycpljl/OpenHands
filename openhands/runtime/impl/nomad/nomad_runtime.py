"""HashiCorp Nomad runtime implementation for OpenHands.

This runtime creates and manages OpenHands sandbox environments using HashiCorp Nomad.
It provides isolated execution environments for agents by deploying Docker containers
through Nomad's job scheduling system.
"""

import json
import os
from typing import Callable, Generator
from urllib.parse import urlparse

import httpx
import tenacity
from tenacity import RetryCallState

from openhands.core.config import OpenHandsConfig
from openhands.core.exceptions import (
    AgentRuntimeError,
    AgentRuntimeNotFoundError,
    AgentRuntimeNotReadyError,
    AgentRuntimeUnavailableError,
)
from openhands.core.logger import openhands_logger as logger
from openhands.events import EventStream
from openhands.integrations.provider import PROVIDER_TOKEN_TYPE
from openhands.runtime.impl.action_execution.action_execution_client import (
    ActionExecutionClient,
)
from openhands.runtime.plugins import PluginRequirement
from openhands.runtime.runtime_status import RuntimeStatus
from openhands.runtime.utils.command import (
    DEFAULT_MAIN_MODULE,
    get_action_execution_server_startup_command,
)
from openhands.utils.async_utils import call_sync_from_async
from openhands.utils.tenacity_stop import stop_if_should_exit


class NomadRuntime(ActionExecutionClient):
    """HashiCorp Nomad runtime for OpenHands.

    This runtime creates isolated sandbox environments using HashiCorp Nomad's
    job scheduling system. Each runtime instance corresponds to a Nomad job
    that runs the OpenHands action execution server in a Docker container.

    Features:
    - Isolated execution environments using Docker containers
    - Dynamic port allocation through Nomad's bridge networking
    - Automatic job lifecycle management (create, monitor, cleanup)
    - Support for custom container images and resource allocation
    - Integration with OpenHands' action execution server

    Configuration:
    - nomad_address: Nomad cluster address (e.g., http://nomad.example.com:4646)
    - nomad_token: Authentication token for Nomad API
    - nomad_datacenter: Target datacenter for job placement
    - nomad_namespace: Nomad namespace (default: "default")
    - container_image: Docker image for the sandbox (default: runtime image)
    - cpu_limit: CPU allocation in MHz (default: 1000)
    - memory_limit: Memory allocation in MB (default: 2048)
    """

    def __init__(
        self,
        config: OpenHandsConfig,
        event_stream: EventStream,
        sid: str = 'default',
        plugins: list[PluginRequirement] | None = None,
        env_vars: dict[str, str] | None = None,
        status_callback: Callable[..., None] | None = None,
        attach_to_existing: bool = False,
        headless_mode: bool = True,
        user_id: str | None = None,
        git_provider_tokens: PROVIDER_TOKEN_TYPE | None = None,
        main_module: str = DEFAULT_MAIN_MODULE,
    ) -> None:
        super().__init__(
            config,
            event_stream,
            sid,
            plugins,
            env_vars,
            status_callback,
            attach_to_existing,
            headless_mode,
            user_id,
            git_provider_tokens,
        )

        # Nomad configuration
        self.nomad_address = config.sandbox.nomad_address or 'http://localhost:4646'
        self.nomad_token = config.sandbox.nomad_token
        self.nomad_datacenter = config.sandbox.nomad_datacenter or 'dc1'
        self.nomad_namespace = config.sandbox.nomad_namespace or 'default'

        # Container configuration
        self.container_image = (
            config.sandbox.runtime_container_image
            or 'ghcr.io/all-hands-ai/runtime:0.43-nikolaik'
        )
        self.cpu_limit = config.sandbox.nomad_cpu_limit or 1000
        self.memory_limit = config.sandbox.nomad_memory_limit or 2048

        # Runtime state
        self.job_id: str | None = None
        self.allocation_id: str | None = None
        self.runtime_url: str | None = None
        self._runtime_initialized: bool = False
        self.main_module = main_module

        # Setup HTTP session for Nomad API
        self.nomad_session = httpx.Client(timeout=30.0)
        if self.nomad_token:
            self.nomad_session.headers.update({'X-Nomad-Token': self.nomad_token})

    def log(self, level: str, message: str, exc_info: bool | None = None) -> None:
        getattr(logger, level)(
            message,
            stacklevel=2,
            exc_info=exc_info,
            extra={
                'session_id': self.sid,
                'job_id': self.job_id,
                'allocation_id': self.allocation_id,
            },
        )

    @property
    def action_execution_server_url(self) -> str:
        if self.runtime_url is None:
            raise NotImplementedError('Runtime URL is not initialized')
        return self.runtime_url

    async def connect(self) -> None:
        """Connect to or create a Nomad runtime environment."""
        try:
            await call_sync_from_async(self._start_or_attach_to_runtime)
        except Exception:
            self.close()
            self.log('error', 'Runtime failed to start', exc_info=True)
            raise
        await call_sync_from_async(self.setup_initial_env)
        self._runtime_initialized = True

    def _start_or_attach_to_runtime(self) -> None:
        """Start a new runtime or attach to an existing one."""
        self.log('info', 'Starting or attaching to Nomad runtime')

        existing_job = self._check_existing_job()
        if existing_job:
            self.log('info', f'Using existing job with ID: {self.job_id}')
        elif self.attach_to_existing:
            self.log('info', f'Failed to find existing job for SID: {self.sid}')
            raise AgentRuntimeNotFoundError(
                f'Could not find existing Nomad job for SID: {self.sid}'
            )
        else:
            self.log('info', 'No existing job found, creating a new one')
            self.set_runtime_status(RuntimeStatus.BUILDING_RUNTIME)
            self._create_nomad_job()

        assert self.job_id is not None, 'Job ID is not set'

        self.set_runtime_status(RuntimeStatus.STARTING_RUNTIME)
        if not self.attach_to_existing:
            self.log('info', 'Waiting for job to be running...')
        self._wait_until_running()
        if not self.attach_to_existing:
            self.log('info', 'Runtime is ready.')
        self.set_runtime_status(RuntimeStatus.READY)

    def _check_existing_job(self) -> bool:
        """Check if a job already exists for this session."""
        job_id = f'openhands-runtime-{self.sid}'
        self.log('info', f'Checking for existing job: {job_id}')

        try:
            response = self._send_nomad_request('GET', f'/v1/job/{job_id}')
            job_data = response.json()
            status = job_data.get('Status')
            self.log('info', f'Found job with status: {status}')

            if status == 'running':
                self.job_id = job_id
                self._get_allocation_info()
                return True
            elif status == 'dead':
                self.log('info', 'Found job but it is dead, will create new one')
                return False
            else:
                self.log('info', f'Found job with status {status}, will create new one')
                return False

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self.log('info', f'No existing job found: {job_id}')
                return False
            self.log('error', f'Error checking for existing job: {e}')
            raise
        except Exception as e:
            self.log('error', f'Unexpected error checking for job: {e}')
            raise

    def _create_nomad_job(self) -> None:
        """Create a new Nomad job for the runtime."""
        job_id = f'openhands-runtime-{self.sid}'
        self.job_id = job_id

        # Get startup command for the action execution server
        startup_command = self.get_action_execution_server_startup_command()

        # Parse command into executable and args
        # startup_command is a list, so we can use it directly
        command = startup_command[0] if startup_command else 'python'
        args = startup_command[1:] if len(startup_command) > 1 else []

        # Prepare environment variables
        environment = self._prepare_environment_variables()

        # Volume mounts are not supported in this version

        # Create job specification
        job_spec = {
            'Job': {
                'ID': job_id,
                'Name': job_id,
                'Type': 'service',
                'Datacenters': [self.nomad_datacenter],
                'Namespace': self.nomad_namespace,
                'TaskGroups': [
                    {
                        'Name': 'runtime',
                        'Count': 1,
                        'Networks': [
                            {
                                'Mode': 'bridge',
                                'DynamicPorts': [{'Label': 'http', 'To': 8080}],
                            }
                        ],
                        'Tasks': [
                            {
                                'Name': 'sandbox',
                                'Driver': 'docker',
                                'Config': {
                                    'image': self.container_image,
                                    'ports': ['http'],
                                    'command': command,
                                    'args': args,
                                    'work_dir': '/openhands/code',
                                },
                                'Env': environment,
                                'Resources': self._get_resource_config(),
                            }
                        ],
                    }
                ],
            }
        }

        self.log('info', f'Creating Nomad job: {job_id}')
        self.log('debug', f'Job specification: {json.dumps(job_spec, indent=2)}')

        try:
            response = self._send_nomad_request('POST', '/v1/jobs', json=job_spec)
            result = response.json()
            self.log(
                'info', f'Job created successfully. Eval ID: {result.get("EvalID")}'
            )
        except Exception as e:
            self.log('error', f'Failed to create Nomad job: {e}')
            raise AgentRuntimeUnavailableError(
                f'Failed to create Nomad job: {e}'
            ) from e

    def _get_allocation_info(self) -> None:
        """Get allocation information for the job."""
        if not self.job_id:
            raise RuntimeError('Job ID not set')

        try:
            response = self._send_nomad_request(
                'GET', f'/v1/job/{self.job_id}/allocations'
            )
            allocations = response.json()

            if not allocations:
                raise AgentRuntimeError('No allocations found for job')

            # Find a running allocation
            running_alloc = None
            for alloc in allocations:
                if alloc.get('ClientStatus') == 'running':
                    running_alloc = alloc
                    break

            if not running_alloc:
                raise AgentRuntimeNotReadyError('No running allocation found')

            self.allocation_id = running_alloc['ID']
            node_id = running_alloc['NodeID']

            # Get node information to find the address
            node_response = self._send_nomad_request('GET', f'/v1/node/{node_id}')
            node_data = node_response.json()
            # Extract just the IP address, not the full HTTPAddr which includes port
            node_address = node_data.get('Address', '')
            if not node_address:
                # Fallback to HTTPAddr but extract just the IP part
                http_addr = node_data.get('HTTPAddr', '')
                if ':' in http_addr:
                    node_address = http_addr.split(':')[0]
                else:
                    node_address = http_addr

            # Get allocation details to find the port
            alloc_response = self._send_nomad_request(
                'GET', f'/v1/allocation/{self.allocation_id}'
            )
            alloc_data = alloc_response.json()

            # Extract port from allocation
            port = None

            # Try to get port from AllocatedResources.Shared.Ports first
            allocated_resources = alloc_data.get('AllocatedResources', {})
            shared_resources = allocated_resources.get('Shared', {})
            ports = shared_resources.get('Ports', [])

            for port_info in ports:
                if port_info.get('Label') == 'http':
                    port = port_info.get('Value')
                    break

            # Fallback to checking Networks if not found in Ports
            if not port:
                networks = shared_resources.get('Networks', [])
                for network in networks:
                    dynamic_ports = network.get('DynamicPorts', [])
                    for port_info in dynamic_ports:
                        if port_info.get('Label') == 'http':
                            port = port_info.get('Value')
                            break
                    if port:
                        break

            if not port:
                raise AgentRuntimeError('Could not find allocated port')

            # Handle IP address mapping for cloud environments
            # This supports both scenarios:
            # 1. Single IP environment: no mapping needed, use original IP
            # 2. Multi-node environment: map internal IPs to external IPs as configured
            if self.config.sandbox.nomad_ip_mapping:
                mapped_ip = self.config.sandbox.nomad_ip_mapping.get(node_address)
                if mapped_ip:
                    self.log(
                        'info',
                        f'Mapping internal IP {node_address} to external IP {mapped_ip}',
                    )
                    node_address = mapped_ip
                else:
                    self.log(
                        'debug',
                        f'No mapping configured for IP {node_address}, using original IP',
                    )
            else:
                self.log(
                    'debug',
                    f'No IP mapping configured, using original IP {node_address}',
                )

            self.runtime_url = f'http://{node_address}:{port}'
            self.log('info', f'Runtime URL: {self.runtime_url}')

        except Exception as e:
            self.log('error', f'Failed to get allocation info: {e}')
            raise

    def _wait_until_running(self) -> None:
        """Wait until the job allocation is running and healthy."""
        retry_decorator = tenacity.retry(
            stop=tenacity.stop_after_delay(300)  # 5 minutes timeout
            | stop_if_should_exit()
            | self._stop_if_closed,
            reraise=True,
            retry=tenacity.retry_if_exception_type(AgentRuntimeNotReadyError),
            wait=tenacity.wait_fixed(5),
        )
        retry_decorator(self._wait_until_running_impl)()

    def _wait_until_running_impl(self) -> None:
        """Implementation of waiting for job to be running."""
        if not self.job_id:
            raise RuntimeError('Job ID not set')

        self.log('debug', f'Checking job status: {self.job_id}')

        try:
            # Check job status
            response = self._send_nomad_request('GET', f'/v1/job/{self.job_id}')
            job_data = response.json()
            job_status = job_data.get('Status')

            if job_status != 'running':
                raise AgentRuntimeNotReadyError(
                    f'Job status is {job_status}, not running'
                )

            # Get allocation info
            self._get_allocation_info()

            # Test if the action execution server is responding
            if self.runtime_url:
                try:
                    health_response = self.session.get(
                        f'{self.runtime_url}/alive', timeout=5
                    )
                    if health_response.status_code == 200:
                        self.log('debug', 'Action execution server is healthy')
                        return
                    else:
                        raise AgentRuntimeNotReadyError(
                            f'Action execution server not healthy: {health_response.status_code}'
                        )
                except httpx.RequestError as e:
                    raise AgentRuntimeNotReadyError(
                        f'Action execution server not reachable: {e}'
                    )
            else:
                raise AgentRuntimeNotReadyError('Runtime URL not available')

        except AgentRuntimeNotReadyError:
            raise
        except Exception as e:
            self.log('error', f'Error checking job status: {e}')
            raise AgentRuntimeNotReadyError(f'Error checking job status: {e}')

    def _get_resource_config(self) -> dict:
        """Get resource configuration."""
        resources = {
            'CPU': self.cpu_limit,
            'MemoryMB': self.memory_limit,
        }

        # GPU support is not implemented in this version
        if self.config.sandbox.enable_gpu:
            self.log('warning', 'GPU support is not yet implemented for Nomad runtime')

        return resources

    def _prepare_environment_variables(self) -> dict[str, str]:
        """Prepare environment variables for the container.

        Returns:
            Dictionary of environment variables to set in the container.
        """
        environment = {}

        # Start with initial environment variables from parent class
        if hasattr(self, 'initial_env_vars') and self.initial_env_vars:
            environment.update(self.initial_env_vars)

        # Add runtime-specific environment variables
        environment.update(
            {
                'PYTHONUNBUFFERED': '1',
                'PIP_BREAK_SYSTEM_PACKAGES': '1',
                'OPENHANDS_RUNTIME': 'nomad',
            }
        )

        # Add Nomad-specific IDs if available
        if self.job_id:
            environment['OPENHANDS_NOMAD_JOB_ID'] = self.job_id
        if self.allocation_id:
            environment['OPENHANDS_NOMAD_ALLOCATION_ID'] = self.allocation_id

        # Add debug flag if enabled
        if self.config.debug or os.environ.get('DEBUG', 'false').lower() == 'true':
            environment['DEBUG'] = 'true'
            environment['OPENHANDS_DEBUG'] = 'true'

        # Add workspace configuration
        if self.config.workspace_mount_path_in_sandbox:
            environment['WORKSPACE_BASE'] = self.config.workspace_mount_path_in_sandbox

        # Add user configuration
        if hasattr(self.config.sandbox, 'user_id'):
            environment['OPENHANDS_USER_ID'] = str(self.config.sandbox.user_id)

        # Add runtime startup environment variables from config
        if self.config.sandbox.runtime_startup_env_vars:
            environment.update(self.config.sandbox.runtime_startup_env_vars)

        # Add any additional environment variables passed during initialization
        if hasattr(self, 'env_vars') and self.env_vars:
            environment.update(self.env_vars)

        # Filter out None values and ensure all values are strings
        filtered_env = {}
        for key, value in environment.items():
            if value is not None:
                filtered_env[key] = str(value)

        self.log('debug', f'Prepared {len(filtered_env)} environment variables')
        return filtered_env

    def _send_nomad_request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Send a request to the Nomad API."""
        url = f'{self.nomad_address.rstrip("/")}{path}'

        try:
            response = self.nomad_session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            self.log(
                'error', f'Nomad API error: {e.response.status_code} {e.response.text}'
            )
            raise
        except Exception as e:
            self.log('error', f'Nomad API request failed: {e}')
            raise

    def _stop_if_closed(self, retry_state: RetryCallState) -> bool:
        """Stop retrying if the runtime has been closed."""
        return self._runtime_closed

    def get_action_execution_server_startup_command(self) -> list[str]:
        """Get the startup command for the action execution server."""
        return get_action_execution_server_startup_command(
            server_port=8080,  # Fixed port for Nomad containers
            plugins=self.plugins,
            app_config=self.config,
            main_module=self.main_module,
            override_user_id=1000,  # Use non-root user ID
            override_username='openhands',  # Use openhands username
        )

    @property
    def vscode_url(self) -> str | None:
        """Get VSCode URL if available."""
        token = super().get_vscode_token()
        if not token or not self.runtime_url:
            return None

        parsed_url = urlparse(self.runtime_url)
        vscode_url = f'{parsed_url.scheme}://vscode-{parsed_url.netloc}/?tkn={token}&folder={self.config.workspace_mount_path_in_sandbox}'
        self.log('debug', f'VSCode URL: {vscode_url}')
        return vscode_url

    @property
    def web_hosts(self) -> dict[str, int]:
        """Get available web hosts."""
        # For Nomad runtime, we don't have predefined web hosts
        # The allocation provides dynamic ports
        return {}

    def close(self) -> None:
        """Close the runtime and clean up resources."""
        self._runtime_closed = True

        if self.job_id:
            self.log('info', f'Stopping Nomad job: {self.job_id}')
            try:
                self._send_nomad_request('DELETE', f'/v1/job/{self.job_id}')
                self.log('info', 'Job stopped successfully')
            except Exception as e:
                self.log('error', f'Failed to stop job: {e}')

        if hasattr(self, 'nomad_session'):
            self.nomad_session.close()

        super().close()

    def pause(self) -> None:
        """Pause the runtime by stopping the Nomad job."""
        if not self.job_id:
            self.log('warning', 'Cannot pause: no job ID available')
            return

        try:
            # Stop the job (but don't purge it)
            stop_payload = {'JobID': self.job_id, 'Purge': False}
            self._send_nomad_request(
                'POST', f'/v1/job/{self.job_id}/stop', json=stop_payload
            )
            self.log('info', f'Job paused: {self.job_id}')
        except Exception as e:
            self.log('error', f'Failed to pause job: {e}')
            raise

    def resume(self) -> None:
        """Resume the runtime by restarting the Nomad job."""
        if not self.job_id:
            self.log('warning', 'Cannot resume: no job ID available')
            return

        try:
            # Get the job specification and resubmit it
            response = self._send_nomad_request('GET', f'/v1/job/{self.job_id}')
            job_data = response.json()

            # Resubmit the job
            job_spec = {'Job': job_data}
            self._send_nomad_request('POST', '/v1/jobs', json=job_spec)
            self.log('info', f'Job resumed: {self.job_id}')

            # Wait for it to be running again
            self._wait_until_running()
        except Exception as e:
            self.log('error', f'Failed to resume job: {e}')
            raise

    def get_logs(
        self, task_name: str = 'sandbox', log_type: str = 'stdout', tail: int = 100
    ) -> str:
        """Get logs from the Nomad allocation.

        Args:
            task_name: Name of the task to get logs from
            log_type: Type of logs ('stdout' or 'stderr')
            tail: Number of lines to tail (0 for all logs)

        Returns:
            Log content as string
        """
        if not self.allocation_id:
            self.log('warning', 'Cannot get logs: no allocation ID available')
            return ''

        try:
            params = {
                'task': task_name,
                'type': log_type,
                'plain': 'true',
            }
            if tail > 0:
                params['tail'] = str(tail)

            response = self._send_nomad_request(
                'GET', f'/v1/client/fs/logs/{self.allocation_id}', params=params
            )
            return response.text
        except Exception as e:
            self.log('error', f'Failed to get logs: {e}')
            return f'Error getting logs: {e}'

    def stream_logs(
        self, task_name: str = 'sandbox', log_type: str = 'stdout', follow: bool = True
    ) -> Generator[str, None, None]:
        """Stream logs from the Nomad allocation.

        Args:
            task_name: Name of the task to stream logs from
            log_type: Type of logs ('stdout' or 'stderr')
            follow: Whether to follow the log stream

        Yields:
            Log lines as they become available
        """
        if not self.allocation_id:
            self.log('warning', 'Cannot stream logs: no allocation ID available')
            return

        try:
            params = {
                'task': task_name,
                'type': log_type,
                'plain': 'true',
                'follow': str(follow).lower(),
            }

            # For streaming, we need to handle the response differently
            url = f'{self.nomad_address.rstrip("/")}/v1/client/fs/logs/{self.allocation_id}'

            headers = {}
            if self.nomad_token:
                headers['X-Nomad-Token'] = self.nomad_token

            with httpx.stream('GET', url, params=params, headers=headers) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        yield line.decode('utf-8')
        except Exception as e:
            self.log('error', f'Failed to stream logs: {e}')
            yield f'Error streaming logs: {e}'

    @classmethod
    async def delete(cls, conversation_id: str) -> None:
        """Delete a runtime by conversation ID."""
        # This would require additional configuration to connect to Nomad
        # For now, we'll just log that deletion was requested
        logger.info(f'Delete requested for conversation: {conversation_id}')
