#!/usr/bin/env python
# openvpn-indicator v1.0
# GTK3 indicator for Ubuntu Unity
import os, subprocess
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, GLib, AppIndicator3 as AppIndicator


SERVICE_NAME='openvpn@client'
STATUS_COMMAND='systemctl status --no-pager {service_name}'.format(service_name=SERVICE_NAME)
START_COMMAND='systemctl start {service_name}'.format(service_name=SERVICE_NAME)
STOP_COMMAND='systemctl stop {service_name}'.format(service_name=SERVICE_NAME)
RESTART_COMMAND='systemctl restart {service_name}'.format(service_name=SERVICE_NAME)
SUDO_COMMAND='gksudo {command}'
FREQUENCY = 60 # seconds
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
        self.ind.set_attention_icon(BASEPATH+'white_lock2.png')
        self.setup_menu()

    def icon_orange(self):
        self.ind.set_icon(BASEPATH+'white_scaled.png')
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
    def icon_red(self):
        self.ind.set_icon(BASEPATH+'white_scaled.png')
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
    def icon_green(self):
        self.ind.set_status(AppIndicator.IndicatorStatus.ATTENTION)

    def setup_menu(self):
        self.menu = Gtk.Menu()

        proc = subprocess.Popen(STATUS_COMMAND.split(' '), stdout=subprocess.PIPE, shell=False)
        vpnStatus = proc.wait()
        self.isRunning = vpnStatus == 0

        # Start
        if(not self.isRunning):
            item = Gtk.MenuItem()
            item.set_label("Connect VPN")
            item.connect("activate", self.handler_menu_start)
            item.show()
            self.menu.append(item)

        # Stop
        if(self.isRunning):
            item = Gtk.MenuItem()
            item.set_label("Disconnect VPN")
            item.connect("activate", self.handler_menu_stop)
            item.show()
            self.menu.append(item)

        # Restart
        if(self.isRunning):
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
        self.setup_menu()
        if self.isRunning:
            self.icon_green()
        else:
            self.icon_red()
        return 1

    def main(self):
        self.checkStatus()
        GLib.timeout_add(FREQUENCY * 1000, self.checkStatus)
        Gtk.main()

if __name__ == "__main__":
    ind = OpenVpnIndicator()
    ind.main()
