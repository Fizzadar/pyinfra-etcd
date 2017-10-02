# pyinfra etcd
# File: pyinfra_etcd/util.py
# Desc: general utilities!

from os import path


def get_template_path(template):
    return path.join(
        path.dirname(__file__),
        'templates',
        template,
    )


def try_get_data(datas, *keys):
    for key in keys:
        data = getattr(datas, key)

        if data is not None:
            return data


def get_urls(host, type_):
    listen_urls = []

    interface = try_get_data(
        host.data,
        'etcd_{0}_interface'.format(type_),
        'etcd_interface',
    )

    interface_type = try_get_data(
        host.data,
        'etcd_{0}_interface_type'.format(type_),
        'etcd_interface_type',
    )

    # Is localhost allowed? (Clients yes, peers no)
    localhost = False
    if type_ == 'client':
        localhost = try_get_data(
            host.data,
            'etcd_{0}_listen_localhost',
            'etcd_listen_localhost',
        )

    # No interface? Listen everywhere
    if not interface:
        listen_urls.append('0.0.0.0')

    # Bind to an interface?
    else:
        network_device = host.fact.network_devices[host.data.etcd_interface]

        # Of one specific type?
        if interface_type:
            listen_urls.append(
                interface[host.data.etcd_interface_type]['address'],
            )

        # Or any IPs on the interface
        else:
            if network_device['ipv4']:
                listen_urls.append(network_device['ipv4']['address'])
            if network_device['ipv6']:
                listen_urls.append('[{0}]'.format(network_device['ipv6']['address']))

        # Additionally listen on localhost?
        if localhost:
            listen_urls.append('127.0.0.1')

    # Now get the relevant port
    port = getattr(host.data, 'etcd_{0}_port'.format(type_))

    # Attach the scheme and port to each address
    return [
        'http://{0}:{1}'.format(address, port)
        for address in listen_urls
    ]


def get_cluster_node_urls(inventory):
    cluster_urls = []

    # Either the etcd_nodes group of it exists, or the whole inventory
    for host in inventory.get_group('etcd_nodes', inventory):
        # Get the peer addresses but w/o any localhost entries
        listen_urls = get_urls(host, 'peer')

        # Append the first, with the hostname prefixed
        for url in listen_urls:
            cluster_urls.append('{0}={1}'.format(host.name, url))

    return cluster_urls
