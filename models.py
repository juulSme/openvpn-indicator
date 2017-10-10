from enum import IntEnum, Enum
from logging import getLogger
from typing import Callable

logger = getLogger(__name__)


class VPNState(IntEnum):
    SERVICE_STOPPED = 0
    SERVICE_RUNNING = 1
    ADAPTER_UP = 2
    IP_ALLOCATED = 3
    DOMAIN_KNOWN = 4
    DOMAIN_RESPONSIVE = 5


class WOLState(IntEnum):
    UNRESPONSIVE = 0
    RESPONSIVE = 1


class ConnectionStatus(Enum):
    CONNECTED = 'Connected'
    CONNECTING = 'Connecting'
    DISCONNECTED = 'Disconnected'


class VPNService(object):
    def __init__(self, description: str, service_name: str, adapter: str, state_change_callback: Callable[..., None],
                 ping_domain: str = None):
        self.description = description
        self.service_name = service_name
        self.adapter = adapter
        self.state_change_callback = state_change_callback
        self.ping_domain = ping_domain
        self._state = VPNState.SERVICE_STOPPED  # type: VPNState
        logger.info('VPN service "' + description + '" initialized')

    @property
    def state(self) -> VPNState:
        return self._state

    @state.setter
    def state(self, value: VPNState) -> None:
        if value != self._state:
            logger.info('VPN service "' + self.description + '" state changed to ' + value.name)
            self._state = value
            self.state_change_callback(self)


class WOLMachine(object):
    def __init__(self, name: str, mac: str, domain: str, broadcast_address: str):
        self.name = name
        self.mac = mac
        self.domain = domain
        self.broadcast_address = broadcast_address
        self._state = None  # type: WOLState
        self.update_callable = None  # type: Callable[[WOLMachine], None]
        logger.info('Device "' + name + '" initialized')

    @property
    def state(self) -> WOLState:
        return self._state

    @state.setter
    def state(self, value: WOLState) -> None:
        if value != self._state:
            logger.info('Device "' + self.name + '" state changed to ' + value.name)
            self._state = value
            self.update_callable(self)
