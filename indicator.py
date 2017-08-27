#!/usr/bin/env python3
# openvpn-indicator v1.0
# GTK3 indicator for Ubuntu Unity
from collections import OrderedDict
from typing import Callable, Dict, Union, List

import gi, logging, os, subprocess
from datetime import datetime
from enum import IntEnum, Enum

from my_config import ADAPTER_NAME, SERVICE_NAME, PING_DOMAIN, WOL_MACHINES

gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, GLib, AppIndicator3 as AppIndicator

logging.basicConfig(format='%(levelname)s: %(message)s', level='INFO')
logger = logging.getLogger(__name__)


SERVICE_STATUS_COMMAND = 'systemctl status --no-pager {service_name}'.format(service_name=SERVICE_NAME)
IFCONFIG_STATUS_COMMAND = 'ifconfig {adapter}'.format(adapter=ADAPTER_NAME)
NSLOOKUP_COMMAND = 'host -W 1 {domain}'.format(domain=PING_DOMAIN)
PING_STATUS_COMMAND = 'ping -W 1 -c 1 {domain}'
START_COMMAND = 'systemctl start {service_name}'.format(service_name=SERVICE_NAME)
STOP_COMMAND = 'systemctl stop {service_name}'.format(service_name=SERVICE_NAME)
RESTART_COMMAND = 'systemctl restart {service_name}'.format(service_name=SERVICE_NAME)
WAKE_COMMAND = 'wakeonlan -i {broadcast_address} {mac}'
SUDO_COMMAND = 'gksudo'
PATH = os.path.abspath(__file__).split("/")
DELIMITER = "/"
BASEPATH = DELIMITER.join(PATH[0:len(PATH)-1])+"/pics/"
LOG_FULL_COMMAND_OUTPUT = False


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


class WOLMachine(object):
    def __init__(self, name: str, mac: str, domain: str, broadcast_address: str):
        self.name = name
        self.mac = mac
        self.domain = domain
        self.broadcast_address = broadcast_address
        self._state = None  # type: WOLState
        self.update_callable = None  # type: Callable[[WOLMachine], None]

    @property
    def state(self) -> WOLState:
        return self._state

    @state.setter
    def state(self, value: WOLState) -> None:
        if value != self._state:
            logger.info(self.name + ' state changed to ' + value.name)
            self._state = value
            self.update_callable(self)


class OpenVpnIndicator:
    def __init__(self):
        self._vpn_state = None  # type: VPNState
        self.ip = None  # type: str
        self._poll_frequency = -1  # type: int
        self.poll_frequency_change = False  # type: bool
        self.wol_machines = [WOLMachine(name=m['name'], mac=m['mac'], domain=m['domain'],
                                        broadcast_address=m['broadcast_address'])
                             for m in WOL_MACHINES]  # type: List[WOLMachine]
        self.ind = AppIndicator.Indicator.new(
            "openvpn-indicator",
            "",
            AppIndicator.IndicatorCategory.OTHER)  # type: AppIndicator
        self.menu = Gtk.Menu()  # type: Gtk.Menu
        self.menu_entries = OrderedDict()  # type: OrderedDict[str, Gtk.MenuItem]

        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.ind.set_attention_icon(BASEPATH+'connected.png')
        self.setup_menu()
        self.check_status()
        Gtk.main()

    @property
    def vpn_state(self) -> VPNState:
        return self._vpn_state

    @vpn_state.setter
    def vpn_state(self, value: VPNState) -> None:
        if value != self._vpn_state:
            logger.info('VPN state changed to ' + value.name)
            self._vpn_state = value
            self.update_vpn_entries()

    @property
    def poll_frequency(self) -> int:
        return self._poll_frequency

    @poll_frequency.setter
    def poll_frequency(self, value: int) -> None:
        self.poll_frequency_change = True if value != self.poll_frequency else False
        self._poll_frequency = value

    def get_status(self) -> ConnectionStatus:
        return ConnectionStatus.CONNECTED if self.vpn_state == VPNState.DOMAIN_RESPONSIVE else \
            ConnectionStatus.CONNECTING if self.vpn_state >= VPNState.SERVICE_RUNNING else ConnectionStatus.DISCONNECTED

    @staticmethod
    def create_menu_item(label: str, fc: Callable) -> Gtk.MenuItem:
        menu_item = Gtk.MenuItem()
        menu_item.set_label(label)
        menu_item.connect("activate", fc)
        menu_item.show()
        return menu_item

    @staticmethod
    def create_menu_separator() -> Gtk.SeparatorMenuItem:
        separator = Gtk.SeparatorMenuItem()
        separator.show()
        return separator

    def setup_menu(self) -> None:
        self.menu_entries['title'] = self.create_menu_item('title', lambda x: self.check_status())
        self.menu_entries['separator1'] = self.create_menu_separator()
        self.menu_entries['connect'] = self.create_menu_item('Connect VPN', self.create_subprocess_callable(
            sudo=True, command=START_COMMAND))
        self.menu_entries['disconnect'] = self.create_menu_item('Disconnect VPN', self.create_subprocess_callable(
            sudo=True, command=STOP_COMMAND))
        self.menu_entries['reconnect'] = self.create_menu_item('Reconnect VPN', self.create_subprocess_callable(
            sudo=True, command=RESTART_COMMAND))
        self.menu_entries['separator2'] = self.create_menu_separator()
        for m in self.wol_machines:
            menu_entry = self.create_menu_item(
                'Wake {name}'.format(name=m.name), self.create_subprocess_callable(
                    sudo=False, command=WAKE_COMMAND.format(broadcast_address=m.broadcast_address, mac=m.mac)
                )
            )
            m.update_callable = self.create_wol_machine_update_callable(menu_entry)
            self.menu_entries[m.name] = menu_entry
        if len(self.wol_machines) > 0:
            self.menu_entries['separator3'] = self.create_menu_separator()
        self.menu_entries['exit'] = self.create_menu_item('Exit OpenVPN Indicator', lambda x: exit(0))

        for entry in self.menu_entries.values():
            self.menu.append(entry)

        self.menu.show()
        self.ind.set_menu(self.menu)

    def update_vpn_entries(self) -> None:
        logger.debug('Updating VPN')

        self.menu_entries['title'].set_label(
            self.get_status().value + '\nService {service}'.format(service=SERVICE_NAME) + (
                ' stopped' if self.vpn_state < VPNState.SERVICE_RUNNING else (
                ' running\nAdapter {adapter}'.format(adapter=ADAPTER_NAME) + (
                    ' down' if self.vpn_state < VPNState.ADAPTER_UP else (
                    ' up ' + (
                        'but no IP is assigned' if self.vpn_state < VPNState.IP_ALLOCATED else (
                        'with IP {ip} assigned'.format(ip=self.ip) + '\nDomain {domain}'.format(domain=PING_DOMAIN) + (
                            ' unknown' if self.vpn_state < VPNState.DOMAIN_KNOWN else (
                            ' known ' + (
                                'but not responsive' if self.vpn_state < VPNState.DOMAIN_RESPONSIVE else
                                'and responsive'
                            ))
                        ))
                    ))
                ))
            )
        )

        if self.get_status() == ConnectionStatus.CONNECTED:
            self.menu_entries['connect'].hide()
            self.menu_entries['disconnect'].show()
            self.menu_entries['reconnect'].show()
            self.ind.set_status(AppIndicator.IndicatorStatus.ATTENTION)
            self.poll_frequency = 30
        elif self.get_status() == ConnectionStatus.CONNECTING:
            self.menu_entries['connect'].hide()
            self.menu_entries['disconnect'].show()
            self.menu_entries['reconnect'].show()
            self.ind.set_icon(BASEPATH + 'connecting.png')
            self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
            self.poll_frequency = 1
        else:  # disconnected
            self.menu_entries['connect'].show()
            self.menu_entries['disconnect'].hide()
            self.menu_entries['reconnect'].hide()
            self.ind.set_icon(BASEPATH + 'disconnected.png')
            self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
            self.poll_frequency = 120

    @staticmethod
    def create_wol_machine_update_callable(menu_entry: Gtk.MenuItem) -> Callable[[WOLMachine, ], None]:
        def func(m: WOLMachine) -> None:
            if m.state == WOLState.RESPONSIVE:
                menu_entry.set_label('{name} is online and responsive'.format(name=m.name))
            else:
                menu_entry.set_label('Wake {name}'.format(name=m.name))
        return func

    @staticmethod
    def run_subprocess(sudo: bool, command: str) -> Dict[str, Union[int, str, bool]]:
        list_command = [SUDO_COMMAND, command] if sudo else command.split(' ')
        command = (SUDO_COMMAND + ' ' if sudo else '') + command

        completed_process = subprocess.run(list_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        success = completed_process.returncode == 0
        out = completed_process.stdout.decode('utf-8')
        err = completed_process.stderr.decode('utf-8')

        if success:
            logger.debug('Executed \"' + command + '\" successfully')
            if LOG_FULL_COMMAND_OUTPUT and len(out) > 0:
                logger.debug('\n' + out)
        else:
            logger.debug('Error executing \"' + command + '\" (exit ' + str(completed_process.returncode) + ')')
            if LOG_FULL_COMMAND_OUTPUT and len(err) > 0:
                logger.debug('\n' + err)

        return {'exit': completed_process.returncode, 'stdout': out, 'stderr': err, 'done': success}

    def create_subprocess_callable(self, sudo: bool, command: str) -> Callable[..., None]:
        def func(evt):
            logger.info('Calling "{sudo}{command}"'.format(sudo='gksudo ' if sudo else '', command=command))
            self.run_subprocess(sudo=sudo, command=command)
            self.check_status()
        return func

    def check_status(self) -> bool:
        logger.debug('Status refreshed at ' + str(datetime.now().time()))

        new_vpn_state = VPNState.SERVICE_STOPPED
        ifconfig_result = False
        ip_line = None

        if self.run_subprocess(sudo=False, command=SERVICE_STATUS_COMMAND)['done']:
            new_vpn_state = VPNState.SERVICE_RUNNING
            ifconfig_result = self.run_subprocess(sudo=False, command=IFCONFIG_STATUS_COMMAND)
        if new_vpn_state >= VPNState.SERVICE_RUNNING and ifconfig_result['done']:
            new_vpn_state = VPNState.ADAPTER_UP
            ip_line = ifconfig_result['stdout'].splitlines()[1].strip()
        if new_vpn_state >= VPNState.ADAPTER_UP and ip_line.startswith('inet addr:'):
            new_vpn_state = VPNState.IP_ALLOCATED
            self.ip = ip_line[10:ip_line.find('  ')]
        if new_vpn_state >= VPNState.IP_ALLOCATED and self.run_subprocess(sudo=False, command=NSLOOKUP_COMMAND)['done']:
            new_vpn_state = VPNState.DOMAIN_KNOWN
        if new_vpn_state >= VPNState.DOMAIN_KNOWN and self.run_subprocess(sudo=False, command=PING_STATUS_COMMAND.format(domain=PING_DOMAIN))['done']:
            new_vpn_state = VPNState.DOMAIN_RESPONSIVE

        self.vpn_state = new_vpn_state

        for m in self.wol_machines:
            if self.run_subprocess(sudo=False, command=PING_STATUS_COMMAND.format(domain=m.domain))['done']:
                m.state = WOLState.RESPONSIVE
            else:
                m.state = WOLState.UNRESPONSIVE

        if self.poll_frequency_change:
            logger.info('Status is "' + self.get_status().name + '", polling frequency set to ' +
                        str(self.poll_frequency) + 's')
            GLib.timeout_add(self.poll_frequency * 1000, self.check_status)
            self.poll_frequency_change = False
            return False
        return True

if __name__ == "__main__":
    ind = OpenVpnIndicator()
