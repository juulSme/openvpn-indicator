# OpenVPN indicator for Unity

![screenshot](./pics/screenshot.png)

OpenVPN service status indicator for Ubuntu's Unity. The applet works by 
polling systemctl (to check if the connection is up) and ifconfig (to check if an 
IP address has been assigned to the tun/tap device). When the service is up but 
the address has not been assigned, it shows as __connecting__, if the address is 
assigned the status changes to __connected__. The connection can be started, 
restarted and stopped from the applet. There is now a menu-item to wake up a machine 
at the end of the tunnel. 

In essence, this is a service indicator. The code can be easily modified to 
indicate the status of any (systemctl) service, not just the OpenVPN service.

##### Instructions

Requires Python, gksudo and OpenVPN. Make a copy of __example_config.py__ called 
__my_config.py__ and modify the variables in the file to reflect your setup. Run with 
```
python indicator.py
```

Add as a startup application using `Launcher -> Startup Applications`.

All dependencies can be installed using
```
sudo apt-get install openvpn gksudo python wakeonlan
``` 