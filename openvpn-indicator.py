#!/usr/bin/env python
# openvpn-indicator v1.0
# GTK3 indicator for Ubuntu Unity
import gi, logging, os, subprocess

from datetime import datetime

gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, GLib, AppIndicator3 as AppIndicator

logging.basicConfig(format='%(levelname)s: %(message)s', level='INFO')
logger = logging.getLogger(__name__)

# change these variables to reflect your setup
SERVICE_NAME = 'openvpn@client_profile'
ADAPTER_NAME = 'tap0'
BROADCAST_ADDRESS = '192.168.1.255'
PING_DOMAIN = 'somemachine.mylan.private'
NUC_MAC = '00:AA:00:AA:00:AA'

SERVICE_STATUS_COMMAND = 'systemctl status --no-pager {service_name}'.format(service_name=SERVICE_NAME)
IFCONFIG_STATUS_COMMAND = 'ifconfig {adapter}'.format(adapter=ADAPTER_NAME)
NSLOOKUP_COMMAND = 'host -W 1 {domain}'.format(domain=PING_DOMAIN)
PING_STATUS_COMMAND = 'ping -c 1 {domain}'.format(domain=PING_DOMAIN)
START_COMMAND = 'systemctl start {service_name}'.format(service_name=SERVICE_NAME)
STOP_COMMAND = 'systemctl stop {service_name}'.format(service_name=SERVICE_NAME)
RESTART_COMMAND = 'systemctl restart {service_name}'.format(service_name=SERVICE_NAME)
WAKE_COMMAND = 'wakeonlan -i {broadcast_address} {mac}'
SUDO_COMMAND = 'gksudo'
PATH = os.path.abspath(__file__).split("/")
DELIMITER = "/"
BASEPATH = DELIMITER.join(PATH[0:len(PATH)-1])+"/pics/"


class OpenVpnIndicator:
    def __init__(self):
        self.ind = AppIndicator.Indicator.new(
            "openvpn-indicator",
            "",
            AppIndicator.IndicatorCategory.OTHER)
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.icon_disconnected()
        self.ind.set_attention_icon(BASEPATH+'connected.png')
        self.setup_menu()
        self.frequency = -1

    def icon_connecting(self):
        self.ind.set_icon(BASEPATH+'connecting.png')
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
    def icon_disconnected(self):
        self.ind.set_icon(BASEPATH+'disconnected.png')
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
    def icon_connected(self):
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
        Gtk.Menu
        self.menu = Gtk.Menu()
        self.menu_title = self.create_menu_item('title', lambda x: self.check_status())
        self.menu_connect = self.create_menu_item('Connect VPN', self.create_subprocess_callable(
            sudo=True, command=START_COMMAND))
        self.menu_disconnect = self.create_menu_item('Disconnect VPN', self.create_subprocess_callable(
            sudo=True, command=STOP_COMMAND))
        self.menu_reconnect = self.create_menu_item('Reconnect VPN', self.create_subprocess_callable(
            sudo=True, command=RESTART_COMMAND))
        self.menu_wake_nuc = self.create_menu_item('Wake NUC', self.create_subprocess_callable(
            sudo=False, command=WAKE_COMMAND.format(broadcast_address=BROADCAST_ADDRESS, mac=NUC_MAC)))
        self.menu_exit = self.create_menu_item('Exit OpenVPN Indicator', lambda x: exit(0))


        self.menu.append(self.menu_title)
        self.menu.append(self.create_menu_separator())
        self.menu.append(self.menu_connect)
        self.menu.append(self.menu_disconnect)
        self.menu.append(self.menu_reconnect)
        self.menu.append(self.menu_wake_nuc)
        self.menu.append(self.create_menu_separator())
        self.menu.append(self.menu_exit)

        self.refresh_menu()
        self.menu.show()
        self.ind.set_menu(self.menu)

    def refresh_menu(self):
        adapter_up = False
        ip_address = False
        dns_returns = False
        domain_returns_ping = False

        service_running = self.run_subprocess(sudo=False, command=SERVICE_STATUS_COMMAND)['done']
        if service_running:
            ifconfig_result = self.run_subprocess(sudo=False, command=IFCONFIG_STATUS_COMMAND)
            adapter_up = ifconfig_result['done']
        if adapter_up:
            ip_line = ifconfig_result['stdout'].splitlines()[1].strip()
            ip_address = False if not ip_line.startswith('inet addr:') else ip_line[10:ip_line.find('  ')]
        if ip_address:
            dns_returns = self.run_subprocess(sudo=False, command=NSLOOKUP_COMMAND)['done']
        if dns_returns:
            domain_returns_ping = self.run_subprocess(sudo=False, command=PING_STATUS_COMMAND)['done']

        self.connected = service_running and domain_returns_ping
        self.connecting = service_running and not self.connected

        self.menu_title.set_label(
            ('Connected' if self.connected else 'Connecting..' if self.connecting else 'Disconnected') +
            '\nService {service}'.format(service=SERVICE_NAME) + (
                ' stopped' if not service_running else (
                ' running\nAdapter {adapter}'.format(adapter=ADAPTER_NAME) + (
                    ' down' if not adapter_up else (
                    ' up ' + (
                        'but no IP is assigned' if not ip_address else (
                        'with IP {ip} assigned'.format(ip=ip_address) + '\nDomain {domain}'.format(domain=PING_DOMAIN) + (
                            ' unknown' if not dns_returns else (
                            ' known ' + (
                                'but not reachable' if not domain_returns_ping else
                                'and reachable'
                            ))
                        ))
                    ))
                ))
            )
        )

        if self.connected:
            self.menu_connect.hide()
            self.menu_disconnect.show()
            self.menu_reconnect.show()
            self.menu_wake_nuc.show()
        elif self.connecting:
            self.menu_connect.hide()
            self.menu_disconnect.show()
            self.menu_reconnect.show()
            self.menu_wake_nuc.hide()
        else:  # disconnected
            self.menu_connect.show()
            self.menu_disconnect.hide()
            self.menu_reconnect.hide()
            self.menu_wake_nuc.hide()

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
        self.refresh_menu()
        if self.connected:
            self.icon_connected()
            desired_frequency = 30
        elif self.connecting:
            self.icon_connecting()
            desired_frequency = 1
        else:
            self.icon_disconnected()
            desired_frequency = 120
        if desired_frequency != self.frequency:
            logger.info('Status poll frequency set to ' + str(desired_frequency) + 's')
            GLib.timeout_add(desired_frequency * 1000, self.check_status)
            self.frequency = desired_frequency
            return False
        return True

    def main(self):
        self.check_status()
        Gtk.main()

if __name__ == "__main__":
    ind = OpenVpnIndicator()
    ind.main()
