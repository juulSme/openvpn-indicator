#!/usr/bin/env python3
# openvpn-indicator v1.0
# GTK3 indicator for Ubuntu Unity
import gi, logging, os, subprocess
from datetime import datetime
from enum import IntEnum, Enum

from my_config import ADAPTER_NAME, SERVICE_NAME, PING_DOMAIN, WOL_MACHINE_NAME, WOL_MAC, WOL_BROADCAST_ADDRESS, \
    WOL_MACHINE_DOMAIN

gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, GLib, AppIndicator3 as AppIndicator

logging.basicConfig(format='%(levelname)s: %(message)s', level='INFO')
logger = logging.getLogger(__name__)


SERVICE_STATUS_COMMAND = 'systemctl status --no-pager {service_name}'.format(service_name=SERVICE_NAME)
IFCONFIG_STATUS_COMMAND = 'ifconfig {adapter}'.format(adapter=ADAPTER_NAME)
NSLOOKUP_COMMAND = 'host -W 1 {domain}'.format(domain=PING_DOMAIN)
PING_STATUS_COMMAND = 'ping -c 1 {domain}'
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


class OpenVpnIndicator:
    def __init__(self):
        self._vpn_state = None
        self._ip = None
        self._nuc_state = None
        self._frequency = -1
        self.frequency_change = False
        self.ind = AppIndicator.Indicator.new(
            "openvpn-indicator",
            "",
            AppIndicator.IndicatorCategory.OTHER)
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.ind.set_attention_icon(BASEPATH+'connected.png')
        self.setup_menu()

    @property
    def vpn_state(self) -> VPNState:
        return self._vpn_state

    @vpn_state.setter
    def vpn_state(self, value: VPNState) -> None:
        if value != self._vpn_state:
            logger.info('VPN state changed to ' + value.name)
            self._vpn_state = value
            self.update_vpn()

    @property
    def nuc_state(self) -> WOLState:
        return self._nuc_state

    @nuc_state.setter
    def nuc_state(self, value: WOLState) -> None:
        if value != self._nuc_state:
            logger.info('NUC state changed to ' + value.name)
            self._nuc_state = value
            self.update_nuc()

    @property
    def frequency(self) -> int:
        return self._frequency

    @frequency.setter
    def frequency(self, value: int) -> None:
        self.frequency_change = True if value != self.frequency else False
        self._frequency = value

    def get_status(self) -> ConnectionStatus:
        return ConnectionStatus.CONNECTED if self.vpn_state == VPNState.DOMAIN_RESPONSIVE else \
            ConnectionStatus.CONNECTING if self.vpn_state >= VPNState.SERVICE_RUNNING else ConnectionStatus.DISCONNECTED

    def create_menu_item(self, label, fc):
        menu_item = Gtk.MenuItem()
        menu_item.set_label(label)
        menu_item.connect("activate", fc)
        menu_item.show()
        return menu_item

    def create_menu_separator(self):
        separator = Gtk.SeparatorMenuItem()
        separator.show()
        return separator

    def setup_menu(self):
        self.menu = Gtk.Menu()
        self.menu_title = self.create_menu_item('title', lambda x: self.check_status())
        self.menu_connect = self.create_menu_item('Connect VPN', self.create_subprocess_callable(
            sudo=True, command=START_COMMAND))
        self.menu_disconnect = self.create_menu_item('Disconnect VPN', self.create_subprocess_callable(
            sudo=True, command=STOP_COMMAND))
        self.menu_reconnect = self.create_menu_item('Reconnect VPN', self.create_subprocess_callable(
            sudo=True, command=RESTART_COMMAND))
        self.menu_wake = self.create_menu_item(
            'Wake {name}'.format(name=WOL_MACHINE_NAME), self.create_subprocess_callable(
                sudo=False, command=WAKE_COMMAND.format(broadcast_address=WOL_BROADCAST_ADDRESS, mac=WOL_MAC)
            )
        )
        self.menu_exit = self.create_menu_item('Exit OpenVPN Indicator', lambda x: exit(0))


        self.menu.append(self.menu_title)
        self.menu.append(self.create_menu_separator())
        self.menu.append(self.menu_connect)
        self.menu.append(self.menu_disconnect)
        self.menu.append(self.menu_reconnect)
        self.menu.append(self.menu_wake)
        self.menu.append(self.create_menu_separator())
        self.menu.append(self.menu_exit)

        self.menu.show()
        self.ind.set_menu(self.menu)

    def update_vpn(self):
        logger.debug('Updating VPN')

        self.menu_title.set_label(
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
            self.menu_connect.hide()
            self.menu_disconnect.show()
            self.menu_reconnect.show()
            self.ind.set_status(AppIndicator.IndicatorStatus.ATTENTION)
            self.frequency = 30
        elif self.get_status() == ConnectionStatus.CONNECTING:
            self.menu_connect.hide()
            self.menu_disconnect.show()
            self.menu_reconnect.show()
            self.ind.set_icon(BASEPATH + 'connecting.png')
            self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
            self.frequency = 1
        else:  # disconnected
            self.menu_connect.show()
            self.menu_disconnect.hide()
            self.menu_reconnect.hide()
            self.ind.set_icon(BASEPATH + 'disconnected.png')
            self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
            self.frequency = 120

    def update_nuc(self):
        logger.debug('Updating NUC')
        if self.nuc_state == WOLState.RESPONSIVE:
            self.menu_wake.set_label('{name} is online and responsive'.format(name=WOL_MACHINE_NAME))
        else:
            self.menu_wake.set_label('Wake {name}'.format(name=WOL_MACHINE_NAME))

    def run_subprocess(self, sudo, command):
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

    def create_subprocess_callable(self, sudo, command):
        def func(evt):
            self.run_subprocess(sudo=sudo, command=command)
            self.check_status()
        return func

    def check_status(self):
        logger.debug('Status refreshed at ' + str(datetime.now().time()))

        new_vpn_state = VPNState.SERVICE_STOPPED
        new_nuc_state = WOLState.UNRESPONSIVE

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
        if self.run_subprocess(sudo=False, command=PING_STATUS_COMMAND.format(domain=WOL_MACHINE_DOMAIN))['done']:
            new_nuc_state = WOLState.RESPONSIVE

        self.vpn_state = new_vpn_state
        self.nuc_state = new_nuc_state

        if self.frequency_change:
            logger.info('Status is "' + self.get_status().name + '", polling frequency set to ' + str(self.frequency) + 's')
            GLib.timeout_add(self.frequency * 1000, self.check_status)
            self.frequency_change = False
            return False
        return True

    def main(self):
        self.check_status()
        Gtk.main()

if __name__ == "__main__":
    ind = OpenVpnIndicator()
    ind.main()
