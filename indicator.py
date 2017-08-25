#!/usr/bin/env python
# openvpn-indicator v1.0
# GTK3 indicator for Ubuntu Unity
import gi, logging, os, subprocess
from datetime import datetime

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


class VPNState(object):
    def __init__(self, signal_menu_refresh, signal_frequency_change):
        self.signal_menu_refresh = signal_menu_refresh
        self.signal_frequency_change = signal_frequency_change
        self.service_running = False
        self.adapter_up = False
        self.ip_address = False
        self.domain_known = False
        self.domain_responsive = False
        self.wol_machine_responsive = False
        self.connected = False
        self.connecting = False
        self.frequency = -1

    def set_with_change_detection(self, key, value):
        if hasattr(self, key) and self.__getattribute__(key) != value:
            super(VPNState, self).__setattr__(key, value)
            if key in ['service_running', 'domain_responsive']:
                self.connected = self.service_running and self.domain_responsive
                self.connecting = self.service_running and not self.connected
            if key not in ['connected', 'connecting', 'frequency']:
                logger.info('State changed: ' + key + ' -> ' + str(value))
                self.signal_menu_refresh()
            if key in ['frequency']:
                self.signal_frequency_change()
        super(VPNState, self).__setattr__(key, value)


class OpenVpnIndicator:
    def __init__(self):
        self.state = VPNState(self.refresh_menu, self.signal_frequency_change)
        self.ind = AppIndicator.Indicator.new(
            "openvpn-indicator",
            "",
            AppIndicator.IndicatorCategory.OTHER)
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.ind.set_attention_icon(BASEPATH+'connected.png')
        self.setup_menu()
        self.frequency_change = False

    def signal_frequency_change(self):
        self.frequency_change = True

    def set_icon_connecting(self):
        self.ind.set_icon(BASEPATH+'connecting.png')
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)

    def set_icon_disconnected(self):
        self.ind.set_icon(BASEPATH+'disconnected.png')
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)

    def set_icon_connected(self):
        self.ind.set_status(AppIndicator.IndicatorStatus.ATTENTION)

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

    def refresh_menu(self):
        logger.debug("Refreshing menu")

        self.menu_title.set_label(
            ('Connected' if self.state.connected else 'Connecting...' if self.state.connecting else 'Disconnected') +
            '\nService {service}'.format(service=SERVICE_NAME) + (
                ' stopped' if not self.state.service_running else (
                ' running\nAdapter {adapter}'.format(adapter=ADAPTER_NAME) + (
                    ' down' if not self.state.adapter_up else (
                    ' up ' + (
                        'but no IP is assigned' if not self.state.ip_address else (
                        'with IP {ip} assigned'.format(ip=self.state.ip_address) + '\nDomain {domain}'.format(domain=PING_DOMAIN) + (
                            ' unknown' if not self.state.domain_known else (
                            ' known ' + (
                                'but not responsive' if not self.state.domain_responsive else
                                'and responsive'
                            ))
                        ))
                    ))
                ))
            )
        )

        if self.state.connected:
            self.menu_connect.hide()
            self.menu_disconnect.show()
            self.menu_reconnect.show()
            self.menu_wake.show()
            self.set_icon_connected()
            self.state.frequency = 30
        elif self.state.connecting:
            self.menu_connect.hide()
            self.menu_disconnect.show()
            self.menu_reconnect.show()
            self.menu_wake.hide()
            self.set_icon_connecting()
            self.state.frequency = 1
        else:  # disconnected
            self.menu_connect.show()
            self.menu_disconnect.hide()
            self.menu_reconnect.hide()
            self.menu_wake.hide()
            self.set_icon_disconnected()
            self.state.frequency = 120

        if self.state.wol_machine_responsive:
            self.menu_wake.set_label('{name} is online and responsive'.format(name=WOL_MACHINE_NAME))
        else:
            self.menu_wake.set_label('Wake {name}'.format(name=WOL_MACHINE_NAME))

    def run_subprocess(self, sudo, command):
        list_command = [SUDO_COMMAND, command] if sudo else command.split(' ')
        command = (SUDO_COMMAND + ' ' if sudo else '') + command

        proc = subprocess.Popen(list_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        exit = proc.wait()
        success = exit == 0
        (out, err) = proc.communicate()

        if success:
            logger.debug('Executed \"' + command + '\" successfully:\n' + out)
        else:
            logger.debug('Error executing \"' + command + '\" (exit ' + str(exit) + ')')
            if len(err) > 0:
                logger.debug('\n' + err)

        return {'exit': exit, 'stdout': out, 'stderr': err, 'done': success}

    def create_subprocess_callable(self, sudo, command):
        def func(evt):
            self.run_subprocess(sudo=sudo, command=command)
            self.check_status()
        return func

    def check_status(self):
        logger.debug('Status refreshed at ' + str(datetime.now().time()))

        self.state.set_with_change_detection('service_running', self.run_subprocess(sudo=False, command=SERVICE_STATUS_COMMAND)['done'])
        if self.state.service_running:
            ifconfig_result = self.run_subprocess(sudo=False, command=IFCONFIG_STATUS_COMMAND)
            self.state.adapter_up = ifconfig_result['done']
        if self.state.adapter_up:
            ip_line = ifconfig_result['stdout'].splitlines()[1].strip()
            self.state.ip_address = False if not ip_line.startswith('inet addr:') else ip_line[10:ip_line.find('  ')]
        if self.state.ip_address:
            self.state.domain_known = self.run_subprocess(sudo=False, command=NSLOOKUP_COMMAND)['done']
        if self.state.domain_known:
            self.state.domain_responsive = self.run_subprocess(sudo=False, command=PING_STATUS_COMMAND.format(domain=PING_DOMAIN))['done']
            self.state.wol_machine_responsive = self.run_subprocess(sudo=False, command=PING_STATUS_COMMAND.format(domain=WOL_MACHINE_DOMAIN))['done']

        if self.frequency_change:
            logger.info('Status is "' + ('Connected' if self.state.connected else 'Connecting' if self.state.connecting
                else 'Disconnected') + '", polling frequency set to ' + str(self.state.frequency) + 's')
            GLib.timeout_add(self.state.frequency * 1000, self.check_status)
            self.frequency_change = False
            return False
        return True

    def main(self):
        self.check_status()
        Gtk.main()

if __name__ == "__main__":
    ind = OpenVpnIndicator()
    ind.main()
