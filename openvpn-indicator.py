#!/usr/bin/env python
# openvpn-indicator v1.0
# GTK3 indicator for Ubuntu Unity
import gi, logging, os, subprocess
from datetime import datetime

gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, GLib, AppIndicator3 as AppIndicator

logging.basicConfig(format='%(message)s', level='INFO')
logger = logging.getLogger(__name__)

# change these variables to reflect your setup
SERVICE_NAME = 'openvpn@client_profile'
ADAPTER_NAME = 'tap0'
PING_DOMAIN = 'somemachine.mylan.private'

SERVICE_STATUS_COMMAND = 'systemctl status --no-pager {service_name}'.format(service_name=SERVICE_NAME)
ADAPTER_STATUS_COMMAND = 'ifconfig {adapter}'.format(adapter=ADAPTER_NAME)
NSLOOKUP_COMMAND = 'nslookup {domain}'.format(domain=PING_DOMAIN)
PING_STATUS_COMMAND = 'ping -c 1 {domain}'.format(domain=PING_DOMAIN)
START_COMMAND = 'systemctl start {service_name}'.format(service_name=SERVICE_NAME)
STOP_COMMAND = 'systemctl stop {service_name}'.format(service_name=SERVICE_NAME)
RESTART_COMMAND = 'systemctl restart {service_name}'.format(service_name=SERVICE_NAME)
SUDO_COMMAND = 'gksudo {command}'
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
        self.icon_red()
        self.ind.set_attention_icon(BASEPATH+'connected.png')
        self.setup_menu()
        self.frequency = -1

    def icon_orange(self):
        self.ind.set_icon(BASEPATH+'connecting.png')
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
    def icon_red(self):
        self.ind.set_icon(BASEPATH+'disconnected.png')
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
    def icon_green(self):
        self.ind.set_status(AppIndicator.IndicatorStatus.ATTENTION)

    def setup_menu(self):
        self.menu = Gtk.Menu()

        adapter_up = False
        dns_returns = False
        domain_returns_ping = False

        proc = subprocess.Popen(SERVICE_STATUS_COMMAND.split(' '), stdout=subprocess.PIPE, shell=False)
        service_running = proc.wait() == 0
        if service_running:
            proc = subprocess.Popen(ADAPTER_STATUS_COMMAND.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    shell=False)
            adapter_up = proc.wait() == 0 and 'inet addr' in proc.communicate()[0]
        if adapter_up:
            proc = subprocess.Popen(NSLOOKUP_COMMAND.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    shell=False)
            dns_returns = proc.wait() == 0
        if dns_returns:
            proc = subprocess.Popen(PING_STATUS_COMMAND.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    shell=False)
            domain_returns_ping = proc.wait() == 0

        self.connected = service_running and domain_returns_ping
        self.connecting = service_running and not self.connected

        # Start
        if(not self.connected):
            item = Gtk.MenuItem()
            item.set_label("Connect VPN")
            item.connect("activate", self.handler_menu_start)
            item.show()
            self.menu.append(item)

        # Stop
        if(self.connected):
            item = Gtk.MenuItem()
            item.set_label("Disconnect VPN")
            item.connect("activate", self.handler_menu_stop)
            item.show()
            self.menu.append(item)

        # Restart
        if(self.connected):
            item = Gtk.MenuItem()
            item.set_label("Restart VPN")
            item.connect("activate", self.handler_menu_restart)
            item.show()
            self.menu.append(item)

        self.menu.show()
        self.ind.set_menu(self.menu)

    def handler_menu_start(self, evt):
        self.icon_orange()
        os.system(SUDO_COMMAND.format(command=START_COMMAND))
        self.checkStatus()

    def handler_menu_stop(self, evt):
        self.icon_orange()
        os.system(SUDO_COMMAND.format(command=STOP_COMMAND))
        self.checkStatus()

    def handler_menu_restart(self, evt):
        self.icon_orange()
        os.system(SUDO_COMMAND.format(command=RESTART_COMMAND))
        self.checkStatus()

    def checkStatus(self):
        logger.debug('Status: connected=' + str(self.connected) + ', connecting=' + str(self.connecting) + ' at ' +
                     str(datetime.now().time()))
        self.setup_menu()
        if self.connected:
            self.icon_green()
            desired_frequency = 30
        elif self.connecting:
            self.icon_orange()
            desired_frequency = 0.5
        else:
            self.icon_red()
            desired_frequency = 120
        if desired_frequency != self.frequency:
            logger.debug('Status poll frequency set to ' + str(desired_frequency) + 's')
            GLib.timeout_add(desired_frequency * 1000, self.checkStatus)
            self.frequency = desired_frequency
            return False
        return True

    def main(self):
        self.checkStatus()
        Gtk.main()

if __name__ == "__main__":
    ind = OpenVpnIndicator()
    ind.main()
