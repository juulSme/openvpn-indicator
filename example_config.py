"""
Make a copy of this file called 'my-config.py' and add the following variables. Modify them to reflect your setup.
"""

SERVICE_NAME = 'openvpn@client_profile'
ADAPTER_NAME = 'tap0'
PING_DOMAIN = 'somemachine.mylan.private'

# For Wake-On-LAN menu entries, a tuple of dicts of details
WOL_MACHINES = (
    {
        'name': 'some_name',
        'domain': 'wol_machine.mylan.private',
        'mac': '00:AA:00:AA:00:AA',
        'broadcast_address': '192.168.1.255',
    },
)
