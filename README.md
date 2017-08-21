# OpenVPN indicator for Unity

Requires Python, gksudo and OpenVPN. Run with 
```
python openvpn-indicator.py
```

Add as a startup application using `Launcher -> Startup Applications`.

Starting, stopping and restarting the OpenVPN connection from the command line requires 
gksudo to be installed.

All dependencies can be installed using
```
sudo apt-get install openvpn gksudo python
``` 

In essence, this is a service indicator. The code can be easily modified to 
indicate the status of any (systemctl) service, not just the OpenVPN service.