import os
import time
from typing import Any, Callable

import httpx
import tenacity

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
    """Runtime implementation that uses HashiCorp Nomad for container orchestration.

    This runtime creates and manages Docker containers through Nomad's API,
    allowing for better scalability and resource management in distributed environments.

    Args:
        config (OpenHandsConfig): The application configuration.
        event_stream (EventStream): The event stream to subscribe to.
        sid (str, optional): The session ID. Defaults to 'default'.
        plugins (list[PluginRequirement] | None, optional): List of plugin requirements. Defaults to None.
        env_vars (dict[str, str] | None, optional): Environment variables to set. Defaults to None.
        status_callback (Callable | None, optional): Status callback function. Defaults to None.
        attach_to_existing (bool, optional): Whether to attach to existing job. Defaults to False.
        headless_mode (bool, optional): Whether to run in headless mode. Defaults to True.
        user_id (str | None, optional): User ID. Defaults to None.
        git_provider_tokens (PROVIDER_TOKEN_TYPE | None, optional): Git provider tokens. Defaults to None.
        main_module (str, optional): Main module to run. Defaults to DEFAULT_MAIN_MODULE.
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
        self.nomad_address = config.sandbox.nomad_address or os.environ.get(
            'NOMAD_ADDR', 'http://localhost:4646'
        )
        self.nomad_token = config.sandbox.nomad_token or os.environ.get('NOMAD_TOKEN')
        self.nomad_namespace = config.sandbox.nomad_namespace or os.environ.get(
            'NOMAD_NAMESPACE', 'default'
        )
        self.nomad_datacenter = config.sandbox.nomad_datacenter or os.environ.get(
            'NOMAD_DATACENTER', 'dc1'
        )
        
        # Service discovery configuration (requires Consul)
        # Priority: config.toml > environment variable > default (True)
        if config.sandbox.nomad_enable_service_discovery is not None:
            self.enable_service_discovery = config.sandbox.nomad_enable_service_discovery
        else:
            self.enable_service_discovery = os.environ.get(
                'NOMAD_ENABLE_SERVICE_DISCOVERY', 'true'
            ).lower() in ('true', '1', 'yes')
        
        # Network configuration
        # Supported modes: bridge, host, none, or custom network name
        self.network_mode = os.environ.get('NOMAD_NETWORK_MODE', 'bridge')
        self.custom_network = os.environ.get('NOMAD_CUSTOM_NETWORK', None)

        # Job configuration
        self.job_id = f'openhands-runtime-{sid}'
        self.job_name = self.job_id
        self.container_image = (
            config.sandbox.runtime_container_image
            or config.sandbox.base_container_image
        )
        self.main_module = main_module

        # Runtime state
        self.allocation_id: str | None = None
        self.runtime_url: str | None = None
        self.container_port = 60000  # Default port for action execution server
        self._runtime_initialized = False

        # HTTP client for Nomad API
        self.nomad_client = httpx.Client(
            base_url=self.nomad_address, headers=self._get_nomad_headers(), timeout=30.0
        )

        if not self.container_image:
            raise ValueError(
                'Container image is required for Nomad runtime. '
                'Please set runtime_container_image or base_container_image in config.'
            )

    def _get_nomad_headers(self) -> dict[str, str]:
        """Get headers for Nomad API requests."""
        headers = {'Content-Type': 'application/json'}
        if self.nomad_token:
            headers['X-Nomad-Token'] = self.nomad_token
        return headers

    def log(self, level: str, message: str, exc_info: bool | None = None) -> None:
        """Log message with runtime context."""
        extra = {'session_id': self.sid}
        if hasattr(self, 'job_id'):
            extra['job_id'] = self.job_id
        if hasattr(self, 'allocation_id') and self.allocation_id:
            extra['allocation_id'] = self.allocation_id

        getattr(logger, level)(
            message,
            stacklevel=2,
            exc_info=exc_info,
            extra=extra,
        )

    @property
    def action_execution_server_url(self) -> str:
        """Get the URL for the action execution server."""
        if self.runtime_url is None:
            raise NotImplementedError('Runtime URL is not initialized')
        return self.runtime_url

    async def connect(self) -> None:
        """Connect to or create the Nomad job."""
        try:
            await call_sync_from_async(self._start_or_attach_to_job)
        except Exception:
            self.close()
            self.log('error', 'Runtime failed to start', exc_info=True)
            raise
        await call_sync_from_async(self.setup_initial_env)
        self._runtime_initialized = True

    def _start_or_attach_to_job(self) -> None:
        """Start a new Nomad job or attach to existing one."""
        self.log('info', 'Starting or attaching to Nomad job')

        existing_job = self._check_existing_job()
        if existing_job and self.attach_to_existing:
            self.log('info', f'Using existing job: {self.job_id}')
            self._get_job_allocation_info()
        elif self.attach_to_existing:
            self.log('info', f'Failed to find existing job: {self.job_id}')
            raise AgentRuntimeNotFoundError(
                f'Could not find existing job: {self.job_id}'
            )
        else:
            self.log(
                'info', 'No existing job found or not attaching, starting a new one'
            )
            self._start_job()

        assert self.allocation_id is not None, 'Allocation ID is not set'
        assert self.runtime_url is not None, 'Runtime URL is not set'

        self.set_runtime_status(RuntimeStatus.STARTING_RUNTIME)
        if not self.attach_to_existing:
            self.log('info', 'Waiting for runtime to be alive...')
        self._wait_until_alive()
        if not self.attach_to_existing:
            self.log('info', 'Runtime is ready.')
        self.set_runtime_status(RuntimeStatus.READY)

    def _check_existing_job(self) -> bool:
        """Check if a job with the same ID already exists."""
        try:
            response = self.nomad_client.get(f'/v1/job/{self.job_id}')
            if response.status_code == 200:
                job_data = response.json()
                status = job_data.get('Status')
                self.log('info', f'Found existing job with status: {status}')
                return status in ['running', 'pending']
            elif response.status_code == 404:
                self.log('info', f'No existing job found: {self.job_id}')
                return False
            else:
                response.raise_for_status()
        except httpx.HTTPError as e:
            self.log('error', f'Error checking existing job: {e}')
            raise
        return False

    def _start_job(self) -> None:
        """Start a new Nomad job."""
        self.log('info', f'Starting new Nomad job: {self.job_id}')
        self.set_runtime_status(RuntimeStatus.STARTING_RUNTIME)

        job_spec = self._create_job_spec()

        try:
            response = self.nomad_client.post('/v1/jobs', json={'Job': job_spec})
            response.raise_for_status()

            job_response = response.json()
            eval_id = job_response.get('EvalID')
            self.log('info', f'Job submitted with evaluation ID: {eval_id}')

            # Wait for job to be scheduled and get allocation
            self._wait_for_allocation()

        except httpx.HTTPError as e:
            self.log('error', f'Failed to start Nomad job: {e}')
            if hasattr(e, 'response') and e.response:
                self.log('error', f'Response: {e.response.text}')
            raise AgentRuntimeUnavailableError() from e

    def _create_job_spec(self) -> dict[str, Any]:
        """Create Nomad job specification."""
        # Prepare environment variables
        environment = dict(**self.initial_env_vars)
        environment.update(
            {
                'port': str(self.container_port),
                'PYTHONUNBUFFERED': '1',
                'PIP_BREAK_SYSTEM_PACKAGES': '1',
            }
        )
        if self.config.debug:
            environment['DEBUG'] = 'true'
        environment.update(self.config.sandbox.runtime_startup_env_vars)

        # Get startup command
        command = self.get_action_execution_server_startup_command()

        job_spec = {
            'ID': self.job_id,
            'Name': self.job_name,
            'Type': 'service',
            'Datacenters': [self.nomad_datacenter],
            'Namespace': self.nomad_namespace,
            'TaskGroups': [
                {
                    'Name': 'runtime',
                    'Count': 1,
                    'RestartPolicy': {
                        'Attempts': 3,
                        # Note: Nomad JSON API requires time.Duration fields as nanoseconds (int),
                        # not string format like "5m" which is used in HCL
                        'Interval': 300000000000,  # 5 minutes in nanoseconds
                        'Delay': 25000000000,  # 25 seconds in nanoseconds
                        'Mode': 'fail',
                    },
                    'Tasks': [
                        {
                            'Name': 'action-server',
                            'Driver': 'docker',
                            'Config': {
                                'image': self.container_image,
                                'command': command[0] if command else '/bin/bash',
                                'args': command[1:] if len(command) > 1 else [],
                                'work_dir': '/openhands/code/',
                                'ports': [
                                    'action_server'
                                ],
                            },
                            'Env': environment,
                            'Resources': {
                                'CPU': self.config.sandbox.nomad_cpu or 1000,  # MHz
                                'MemoryMB': self.config.sandbox.nomad_memory
                                or 2048,  # MB
                            },
                            'Networks': self._create_network_config(),
                        }
                    ],
                }
            ],
        }

        # Add service discovery configuration if enabled (requires Consul)
        if self.enable_service_discovery:
            task = job_spec['TaskGroups'][0]['Tasks'][0]
            task['Services'] = [
                {
                    'Name': f'openhands-runtime-{self.sid}',
                    'PortLabel': 'action_server',
                    'Tags': [
                        'openhands',
                        'runtime',
                        f'session-{self.sid}',
                    ],
                    'Checks': [
                        {
                            'Type': 'http',
                            'Path': '/health',
                            # Note: Service check intervals also need nanoseconds in JSON API
                            'Interval': 10000000000,  # 10 seconds in nanoseconds
                            'Timeout': 3000000000,  # 3 seconds in nanoseconds
                        }
                    ],
                }
            ]

        # Add GPU support if enabled
        if self.config.sandbox.enable_gpu:
            gpu_count = self.config.sandbox.nomad_gpu_count or 1
            gpu_type = self.config.sandbox.nomad_gpu_type or 'nvidia/gpu'

            self.log(
                'info',
                f'GPU support enabled, adding {gpu_count} GPU(s) of type {gpu_type} to job spec',
            )

            task_groups = job_spec.get('TaskGroups', [])
            if task_groups and isinstance(task_groups, list):
                tasks = task_groups[0].get('Tasks', [])
                if tasks and isinstance(tasks, list):
                    task = tasks[0]
                    resources = task.get('Resources', {})
                    if isinstance(resources, dict):
                        # Add GPU device requirement
                        resources['Devices'] = [
                            {
                                'Name': gpu_type,
                                'Count': gpu_count,
                            }
                        ]

                    # Add GPU-specific Docker configuration
                    docker_config = task.get('Config', {})
                    if isinstance(docker_config, dict):
                        # Enable GPU runtime for Docker
                        docker_config['runtime'] = 'nvidia'

                        # Add GPU capabilities
                        if 'cap_add' not in docker_config:
                            docker_config['cap_add'] = []
                        docker_config['cap_add'].extend(['SYS_ADMIN'])

                        # Mount GPU devices (for multiple GPUs)
                        gpu_devices = ['/dev/nvidiactl', '/dev/nvidia-uvm']
                        for i in range(gpu_count):
                            gpu_devices.append(f'/dev/nvidia{i}')
                        docker_config['devices'] = gpu_devices

                        # Add NVIDIA environment variables
                        task_env = task.get('Env', {})
                        if isinstance(task_env, dict):
                            task_env.update(
                                {
                                    'NVIDIA_VISIBLE_DEVICES': 'all',
                                    'NVIDIA_DRIVER_CAPABILITIES': 'compute,utility',
                                    'CUDA_VISIBLE_DEVICES': 'all',
                                }
                            )

                        # Add GPU-specific constraints if needed
                        if 'Constraints' not in task:
                            task['Constraints'] = []

                        # Add constraint to ensure the node has the required GPU type
                        task['Constraints'].append(
                            {
                                'LTarget': '${attr.driver.docker.runtime.nvidia}',
                                'RTarget': 'true',
                                'Operand': '=',
                            }
                        )

        return job_spec

    def _create_network_config(self) -> list[dict[str, Any]]:
        """Create network configuration based on network mode."""
        if self.network_mode == 'host':
            # Host networking - container uses host network directly
            # Note: In host mode, no port mapping is needed
            return [
                {
                    'Mode': 'host',
                }
            ]
        elif self.network_mode == 'none':
            # No networking
            return [
                {
                    'Mode': 'none',
                }
            ]
        elif self.custom_network:
            # Custom Docker network
            return [
                {
                    'Mode': 'bridge',
                    'Device': self.custom_network,
                    'DynamicPorts': [
                        {
                            'Label': 'action_server',
                            'To': self.container_port,
                        }
                    ],
                }
            ]
        else:
            # Default bridge networking with dynamic port allocation
            return [
                {
                    'Mode': 'bridge',
                    'DynamicPorts': [
                        {
                            'Label': 'action_server',
                            'To': self.container_port,  # Container internal port
                        }
                    ],
                }
            ]

    def _wait_for_allocation(self) -> None:
        """Wait for job allocation and get allocation info."""
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                response = self.nomad_client.get(f'/v1/job/{self.job_id}/allocations')
                response.raise_for_status()

                allocations = response.json()
                if allocations:
                    # Get the first allocation
                    allocation = allocations[0]
                    alloc_id = allocation['ID']
                    client_status = allocation['ClientStatus']

                    self.log('info', f'Allocation {alloc_id} status: {client_status}')

                    if client_status == 'running':
                        self.allocation_id = alloc_id
                        self._get_allocation_network_info(allocation)
                        return
                    elif client_status in ['failed', 'lost']:
                        raise AgentRuntimeError(
                            f'Allocation failed with status: {client_status}'
                        )

                time.sleep(2)

            except httpx.HTTPError as e:
                self.log('error', f'Error waiting for allocation: {e}')
                raise

        raise AgentRuntimeError('Timeout waiting for job allocation')

    def _get_job_allocation_info(self) -> None:
        """Get allocation info for existing job."""
        try:
            response = self.nomad_client.get(f'/v1/job/{self.job_id}/allocations')
            response.raise_for_status()

            allocations = response.json()
            if not allocations:
                raise AgentRuntimeNotFoundError(
                    f'No allocations found for job: {self.job_id}'
                )

            # Find running allocation
            running_alloc = None
            for alloc in allocations:
                if alloc['ClientStatus'] == 'running':
                    running_alloc = alloc
                    break

            if not running_alloc:
                raise AgentRuntimeNotFoundError(
                    f'No running allocation found for job: {self.job_id}'
                )

            self.allocation_id = running_alloc['ID']
            self._get_allocation_network_info(running_alloc)

        except httpx.HTTPError as e:
            self.log('error', f'Error getting job allocation info: {e}')
            raise

    def _get_allocation_network_info(self, allocation: dict[str, Any]) -> None:
        """Extract network information from allocation."""
        try:
            # Get detailed allocation info to get network details
            response = self.nomad_client.get(f'/v1/allocation/{allocation["ID"]}')
            response.raise_for_status()

            alloc_detail = response.json()
            if not isinstance(alloc_detail, dict):
                raise AgentRuntimeError('Invalid allocation response format')

            resources = alloc_detail.get('Resources', {})
            if not isinstance(resources, dict):
                raise AgentRuntimeError('Invalid resources format in allocation')

            networks = resources.get('Networks', [])
            if not isinstance(networks, list) or not networks:
                raise AgentRuntimeError('No network information found in allocation')

            network = networks[0]
            if not isinstance(network, dict):
                raise AgentRuntimeError('Invalid network format in allocation')

            node_ip = network.get('IP')
            if not isinstance(node_ip, str):
                raise AgentRuntimeError('Invalid IP address in allocation')

            # Find the dynamic port for action_server
            dynamic_ports = network.get('DynamicPorts', [])
            if not isinstance(dynamic_ports, list):
                raise AgentRuntimeError('Invalid dynamic ports format in allocation')

            action_server_port = None

            for port_info in dynamic_ports:
                if (
                    isinstance(port_info, dict)
                    and port_info.get('Label') == 'action_server'
                ):
                    port_value = port_info.get('Value')
                    if isinstance(port_value, int):
                        action_server_port = port_value
                        break

            if not action_server_port:
                raise AgentRuntimeError('Action server port not found in allocation')

            self.runtime_url = f'http://{node_ip}:{action_server_port}'
            self.log('info', f'Runtime URL: {self.runtime_url}')

        except httpx.HTTPError as e:
            self.log('error', f'Error getting allocation network info: {e}')
            raise

    def _wait_until_alive(self) -> None:
        """Wait until the runtime is alive and responding."""
        retry_decorator = tenacity.retry(
            stop=tenacity.stop_after_delay(120)  # 2 minutes timeout
            | stop_if_should_exit()
            | self._stop_if_closed,
            reraise=True,
            retry=tenacity.retry_if_exception_type(AgentRuntimeNotReadyError),
            wait=tenacity.wait_fixed(2),
        )
        retry_decorator(self._wait_until_alive_impl)()

    def _wait_until_alive_impl(self) -> None:
        """Implementation of wait until alive check."""
        self.log('debug', f'Checking if runtime is alive at: {self.runtime_url}')
        try:
            response = self.session.get(f'{self.runtime_url}/health', timeout=5)
            if response.status_code == 200:
                self.log('debug', 'Runtime is alive')
                return
            else:
                raise AgentRuntimeNotReadyError(
                    f'Runtime not ready, status: {response.status_code}'
                )
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise AgentRuntimeNotReadyError(f'Runtime not ready: {e}')

    def _stop_if_closed(self, retry_state) -> bool:
        """Stop retrying if runtime is closed."""
        return self._runtime_closed

    def close(self) -> None:
        """Close the runtime and stop the Nomad job."""
        if self._runtime_closed:
            return

        self._runtime_closed = True
        self.log('info', 'Closing Nomad runtime')

        if hasattr(self, 'job_id') and self.job_id and not self.attach_to_existing:
            try:
                self.log('info', f'Stopping Nomad job: {self.job_id}')
                response = self.nomad_client.delete(f'/v1/job/{self.job_id}')
                if response.status_code in [200, 404]:  # 404 means already deleted
                    self.log('info', f'Successfully stopped job: {self.job_id}')
                else:
                    self.log('warning', f'Failed to stop job: {response.status_code}')
            except Exception as e:
                self.log('error', f'Error stopping Nomad job: {e}')

        try:
            self.nomad_client.close()
        except Exception as e:
            self.log('error', f'Error closing Nomad client: {e}')

        super().close()

    @classmethod
    async def delete(cls, conversation_id: str) -> None:
        """Delete resources associated with a conversation."""
        # This could be implemented to clean up jobs based on conversation ID
        # For now, we rely on the close() method to clean up individual jobs
        pass

    @property
    def vscode_url(self) -> str | None:
        """Get VSCode URL (not implemented for Nomad runtime)."""
        # VSCode integration would require additional setup in Nomad
        # This could be implemented by exposing additional ports and services
        return None

    @property
    def web_hosts(self) -> dict[str, int]:
        """Get available web hosts (not implemented for Nomad runtime)."""
        # This could be implemented to return available ports for web applications
        return {}

    def get_action_execution_server_startup_command(self) -> list[str]:
        """Get the command to start the action execution server."""
        return get_action_execution_server_startup_command(
            server_port=self.container_port,
            plugins=self.plugins,
            app_config=self.config,
            main_module=self.main_module,
        )
