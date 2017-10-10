"""
Make a copy of this file called 'my-config.py' and add the following variables. Modify them to reflect your setup.
"""

# Log settings. To log to the console, set LOGGING FILE = None. For more output, set LOGGING_LEVEL to DEBUG
LOGGING_FILE = None
LOGGING_LEVEL = 'INFO'

# For VPN services, a dict of dicts. Services that define a ping_domain will not be considered connected until the
# domain is known and pingable. Usually this will be self-hosted VPN services.
SERVICES = {
    'PRIVATE_SERVICE': {
        'name': 'My Private VPN Service',
        'service_name': 'openvpn@my.domain',
        'adapter': 'tap0',
        'ping_domain': 'somemachine.mylan.private'
    },
    'PUBLIC_SERVICE': {
        'name': 'Some Public VPN Service',
        'service_name': 'openvpn@public',
        'adapter': 'tun0',
        'ping_domain': None
    },
}

# For Wake-On-LAN menu entries, a tuple of dicts of details
WOL_MACHINES = (
    {
        'name': 'some_name',
        'domain': 'wol_machine.mylan.private',
        'mac': '00:AA:00:AA:00:AA',
        'broadcast_address': '192.168.1.255',
    },
)
