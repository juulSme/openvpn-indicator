#!/usr/bin/env python3
# openvpn-indicator v1.0
# GTK3 indicator for Ubuntu Unity
import logging
import os
import subprocess
from collections import OrderedDict
from datetime import datetime
from enum import Enum
from typing import Dict, Union, List, Callable

import gi

from models import VPNState, WOLState, ConnectionStatus, VPNService, WOLMachine
from my_config import SERVICES, WOL_MACHINES, LOGGING_FILE, LOGGING_LEVEL

gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, GLib, AppIndicator3 as AppIndicator

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=LOGGING_LEVEL, filename=LOGGING_FILE)
logger = logging.getLogger(__name__)

SERVICE_STATUS_COMMAND = 'systemctl status --no-pager {service_name}'
IFCONFIG_STATUS_COMMAND = 'ifconfig {adapter}'
NSLOOKUP_COMMAND = 'host -W 1 {domain}'
PING_STATUS_COMMAND = 'ping -W 1 -c 1 {domain}'
START_COMMAND = 'systemctl start {service_name}'
STOP_COMMAND = 'systemctl stop {service_name}'
RESTART_COMMAND = 'systemctl restart {service_name}'
CURRENT_STOP_COMMAND = ''
CURRENT_RESTART_COMMAND = ''
WAKE_COMMAND = 'wakeonlan -i {broadcast_address} {mac}'
SUDO_COMMAND = 'gksudo'
PATH = os.path.abspath(__file__).split("/")
DELIMITER = "/"
BASEPATH = DELIMITER.join(PATH[0:len(PATH) - 1]) + "/pics/"
LOG_FULL_COMMAND_OUTPUT = False


class OpenVpnIndicator:
    def __init__(self):
        self.services = Enum('VPN Service', sorted({k: VPNService(description=v['name'], service_name=v['service_name'],
                                                                  adapter=v['adapter'], ping_domain=v['ping_domain'],
                                                                  state_change_callback=self.create_vpn_service_update_callable(), )
                                                    for k, v in SERVICES.items()}.items()))
        self.active_service = None
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
        self.ind.set_attention_icon(BASEPATH + 'connected.png')
        self.setup_menu()
        self.check_status()
        Gtk.main()

    @property
    def poll_frequency(self) -> int:
        return self._poll_frequency

    @poll_frequency.setter
    def poll_frequency(self, value: int) -> None:
        if value != self.poll_frequency:
            self.poll_frequency_change = True
        self._poll_frequency = value

    def get_status(self) -> ConnectionStatus:
        service = self.active_service
        state = None if service is None else service.state

        return ConnectionStatus.DISCONNECTED if service is None or state == VPNState.SERVICE_STOPPED else \
            ConnectionStatus.CONNECTING if (state < VPNState.DOMAIN_RESPONSIVE and service.ping_domain is not None) or \
                                            state < VPNState.IP_ALLOCATED else \
            ConnectionStatus.CONNECTED

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
        for s in self.services:
            menu_entry = self.create_menu_item(
                'Connect to {name}'.format(name=s.value.description), self.create_subprocess_callable(
                    sudo=True, command=START_COMMAND.format(service_name=s.value.service_name)
                )
            )
            self.menu_entries[s.name] = menu_entry
        self.menu_entries['disconnect'] = self.create_menu_item('Disconnect VPN', self.create_disconnect_callable())
        self.menu_entries['reconnect'] = self.create_menu_item('Reconnect VPN', self.create_reconnect_callable())
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
        self.update_vpn_entries()

    def update_vpn_entries(self) -> None:
        self.menu_entries['title'].set_label(
            self.get_status().value + '\nService' + (
                's stopped' if self.active_service is None else (
                ' {service} running\nAdapter {adapter}'.format(service=self.active_service.description,
                                                               adapter=self.active_service.adapter) + (
                    ' down' if self.active_service.state < VPNState.ADAPTER_UP else (
                    ' up ' + (
                        'but no IP is assigned' if self.active_service.state < VPNState.IP_ALLOCATED else (
                        'with IP {ip} assigned'.format(ip=self.ip) + (
                            '' if self.active_service.ping_domain is None else (
                            '\nDomain {domain}'.format(domain=self.active_service.ping_domain) + (
                                ' unknown' if self.active_service.state < VPNState.DOMAIN_KNOWN else (
                                ' known ' + (
                                    'but not responsive' if self.active_service.state < VPNState.DOMAIN_RESPONSIVE else
                                    'and responsive'
                                ))
                            ))
                        ))
                    ))
                ))
            )
        )

        if self.get_status() == ConnectionStatus.CONNECTED:
            logger.debug("Showing VPN menu items for status CONNECTED")
            for s in self.services:
                self.menu_entries[s.name].hide()
            self.menu_entries['disconnect'].show()
            self.menu_entries['reconnect'].show()
            self.ind.set_status(AppIndicator.IndicatorStatus.ATTENTION)
            self.poll_frequency = 30
        elif self.get_status() == ConnectionStatus.CONNECTING:
            logger.debug("Showing VPN menu items for status CONNECTING")
            for s in self.services:
                self.menu_entries[s.name].hide()
            self.menu_entries['disconnect'].show()
            self.menu_entries['reconnect'].show()
            self.ind.set_icon(BASEPATH + 'connecting.png')
            self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
            self.poll_frequency = 1
        else:  # disconnected
            logger.debug("Showing VPN menu items for status DISCONNECTED")
            for s in self.services:
                self.menu_entries[s.name].show()
            self.menu_entries['disconnect'].hide()
            self.menu_entries['reconnect'].hide()
            self.ind.set_icon(BASEPATH + 'disconnected.png')
            self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
            self.poll_frequency = 120

    def create_vpn_service_update_callable(self) -> Callable[[VPNService], None]:
        def func(vpn_service: VPNService):
            self.active_service = None if vpn_service.state == VPNState.SERVICE_STOPPED else vpn_service
            self.update_vpn_entries()
        return func

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

    def create_disconnect_callable(self) -> Callable[..., None]:
        def func(evt):
            self.create_subprocess_callable(
                sudo=True, command=STOP_COMMAND.format(
                    service_name=self.active_service.service_name
                )
            )(evt)
        return func

    def create_reconnect_callable(self) -> Callable[..., None]:
        def func(evt):
            self.create_subprocess_callable(
                sudo=True, command=RESTART_COMMAND.format(
                    service_name=self.active_service.service_name
                )
            )(evt)
        return func

    def check_status(self) -> bool:
        logger.debug('Status refreshed at ' + str(datetime.now().time()))

        for s in self.services:
            new_vpn_state = VPNState.SERVICE_STOPPED
            ifconfig_result = False
            ip_line = None

            if \
            self.run_subprocess(sudo=False, command=SERVICE_STATUS_COMMAND.format(service_name=s.value.service_name))['done']:
                new_vpn_state = VPNState.SERVICE_RUNNING
                ifconfig_result = self.run_subprocess(sudo=False, command=IFCONFIG_STATUS_COMMAND.format(adapter=s.value.adapter))
            if new_vpn_state >= VPNState.SERVICE_RUNNING and ifconfig_result['done']:
                new_vpn_state = VPNState.ADAPTER_UP
                ip_line = ifconfig_result['stdout'].splitlines()[1].strip()
            if new_vpn_state >= VPNState.ADAPTER_UP and ip_line.startswith('inet addr:'):
                new_vpn_state = VPNState.IP_ALLOCATED
                self.ip = ip_line[10:ip_line.find('  ')]
            if new_vpn_state >= VPNState.IP_ALLOCATED and self.run_subprocess(sudo=False, command=NSLOOKUP_COMMAND.format(domain=s.value.ping_domain))['done']:
                new_vpn_state = VPNState.DOMAIN_KNOWN
            if new_vpn_state >= VPNState.DOMAIN_KNOWN and self.run_subprocess(sudo=False, command=PING_STATUS_COMMAND.format(domain=s.value.ping_domain))['done']:
                new_vpn_state = VPNState.DOMAIN_RESPONSIVE

            s.value.state = new_vpn_state

        for m in self.wol_machines:
            if self.run_subprocess(sudo=False, command=NSLOOKUP_COMMAND.format(domain=m.domain))['done'] and \
                    self.run_subprocess(sudo=False, command=PING_STATUS_COMMAND.format(domain=m.domain))['done']:
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
