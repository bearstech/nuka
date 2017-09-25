import os
import codecs
import socket
import ctypes
import ctypes.util
from ctypes import (
    Structure, Union, POINTER,
    pointer, get_errno, cast,
    c_ushort, c_byte, c_void_p, c_char_p, c_uint, c_uint16, c_uint32
)


libc = ctypes.CDLL(ctypes.util.find_library('c'))


class struct_sockaddr(Structure):
    _fields_ = [
        ('sa_family', c_ushort),
        ('sa_data', c_byte * 14)
    ]


class struct_sockaddr_in(Structure):
    _fields_ = [
        ('sin_family', c_ushort),
        ('sin_port', c_uint16),
        ('sin_addr', c_byte * 4)
    ]


class struct_sockaddr_in6(Structure):
    _fields_ = [
        ('sin6_family', c_ushort),
        ('sin6_port', c_uint16),
        ('sin6_flowinfo', c_uint32),
        ('sin6_addr', c_byte * 16),
        ('sin6_scope_id', c_uint32)
    ]


class union_ifa_ifu(Union):
    _fields_ = [
        ('ifu_broadaddr', POINTER(struct_sockaddr)),
        ('ifu_dstaddr', POINTER(struct_sockaddr))
    ]


class struct_ifaddrs(Structure):
    pass


struct_ifaddrs._fields_ = [
    ('ifa_next', POINTER(struct_ifaddrs)),
    ('ifa_name', c_char_p),
    ('ifa_flags', c_uint),
    ('ifa_addr', POINTER(struct_sockaddr)),
    ('ifa_netmask', POINTER(struct_sockaddr)),
    ('ifa_ifu', union_ifa_ifu),
    ('ifa_data', c_void_p)
]


def iter_ifaps(ifap):
    ifa = ifap.contents
    if ifa:
        yield ifa
        while ifa.ifa_next:
            ifa = ifa.ifa_next.contents
            yield ifa


def getinfos(ifa):
    try:
        sa = ifa.ifa_addr.contents
    except ValueError:
        raise StopIteration()
    family = sa.sa_family
    addr = None
    if family == socket.AF_INET6:
        sa = cast(pointer(sa), POINTER(struct_sockaddr_in6)).contents
        addr = socket.inet_ntop(family, sa.sin6_addr)
        yield family, {'address': addr}
    elif family == socket.AF_INET:
        sa = cast(pointer(sa), POINTER(struct_sockaddr_in)).contents
        addr = socket.inet_ntop(family, sa.sin_addr)
        sa = ifa.ifa_netmask.contents
        sa = cast(pointer(sa), POINTER(struct_sockaddr_in)).contents
        netmask = socket.inet_ntop(family, sa.sin_addr)
        yield family, {'address': addr, 'netmask': netmask}


def update_inventory(inventory):
    inventory['fqdn'] = socket.getfqdn()
    inventory['hostname'] = socket.gethostname()

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('example.com', 1))  # connect() for UDP doesn't send packets
    inet_addr = s.getsockname()[0]

    ifap = POINTER(struct_ifaddrs)()
    result = libc.getifaddrs(pointer(ifap))
    if result != 0:
        raise RuntimeError(get_errno())
    families = {2: 'AF_INET', 10: 'AF_INET6'}
    ifaces = inventory['ifaces'] = {}
    try:
        for ifa in iter_ifaps(ifap):
            name = ifa.ifa_name.decode('utf8')
            if name == 'lo':
                continue
            d = ifaces.setdefault(name, {
                'index': libc.if_nametoindex(ifa.ifa_name),
                'primary': False,
                'name': name,
            })
            for family, addr in getinfos(ifa):
                if addr:
                    family = families[family][3:].lower()
                    if family == 'inet' and addr['address'] == inet_addr:
                        d['primary'] = True
                    d.setdefault(family, []).append(addr)
                    filename = '/sys/class/net/{0}/address'.format(name)
                    if os.path.isfile(filename):
                        with codecs.open(filename, 'r', 'utf8') as fd:
                            d['macaddress'] = fd.read().strip() or None
        return ifaces
    finally:
        libc.freeifaddrs(ifap)


def finalize_inventory(inventory):
    import ipaddress
    ifaces = inventory['ifaces']
    for iface in ifaces.values():
        for net in iface.get('inet', []):
            try:
                addr = ipaddress.IPv4Address(net['address'])
            except ValueError:
                is_private = None
            else:
                is_private = addr.is_private
            net['is_private'] = is_private


if __name__ == '__main__':
    inventory = {}
    update_inventory(inventory)
    finalize_inventory(inventory)
    print(inventory)
