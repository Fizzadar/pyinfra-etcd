# pyinfra etcd
# File: pyinfra_etcd/etcd.py
# Desc: installs/configures etcd as a systemd service using pyinfra

from os import path

from pyinfra import inventory
from pyinfra.api import deploy, DeployError
from pyinfra.modules import files, init, server

from .defaults import DEFAULTS


def _get_template_path(template):
    return path.join(
        path.dirname(__file__),
        'templates',
        template,
    )


def _try_get_data(datas, *keys):
    for key in keys:
        data = getattr(datas, key)

        if data is not None:
            return data


def _get_urls(host, type_):
    listen_urls = []

    interface = _try_get_data(
        host.data,
        'etcd_{0}_interface'.format(type_),
        'etcd_interface',
    )

    interface_type = _try_get_data(
        host.data,
        'etcd_{0}_interface_type'.format(type_),
        'etcd_interface_type',
    )

    # Is localhost allowed? (Clients yes, peers no)
    localhost = False
    if type_ == 'client':
        localhost = _try_get_data(
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


def _get_cluster_node_urls():
    cluster_urls = []

    # Either the etcd_nodes group of it exists, or the whole inventory
    for host in inventory.get_group('etcd_nodes', inventory):
        # Get the peer addresses but w/o any localhost entries
        listen_urls = _get_urls(host, 'peer')

        # Append the first, with the hostname prefixed
        for url in listen_urls:
            cluster_urls.append('{0}={1}'.format(host.name, url))

    return cluster_urls


@deploy('Deploy etcd', data_defaults=DEFAULTS)
def install_etcd(state, host, enable_service=True):
    if not host.data.etcd_version:
        raise DeployError(
            'No etcd_version set for this host, refusing to install etcd!',
        )

    server.user(
        {'Create the etcd user'},
        'etcd',
        shell='/sbin/nologin',
    )

    files.directory(
        {'Ensure the etcd data directory exists'},
        '{{ host.data.etcd_data_dir }}',
        user='etcd',
        group='etcd',
    )

    files.directory(
        {'Ensure /usr/local/etcd exists'},
        '/usr/local/etcd',
        user='etcd',
        group='etcd',
    )

    # Work out the filename
    version_name = (
        'etcd-{{ host.data.etcd_version }}-linux-'
        '{{ "amd64" if host.fact.arch == "x86_64" else host.fact.arch }}'
    )

    # Work out the download URL
    download_url = (
        '{{ host.data.etcd_download_base_url }}/'
        '{{ host.data.etcd_version }}/'
        '%s.tar.gz'
    ) % version_name

    temp_filename = state.get_temp_filename(
        'etcd-{0}'.format(host.data.etcd_version),
    )

    download_etcd = files.download(
        {'Download etcd'},
        download_url,
        temp_filename,
    )

    # If we downloaded etcd, extract it!
    if download_etcd.changed:
        server.shell(
            {'Extract etcd'},
            'tar -xzf {0} -C /usr/local/etcd'.format(temp_filename),
        )

    # If the bin links don't exist or we just downloaded etcd, (re)link it!
    etcd_link = host.fact.link('/usr/local/bin/etcd')
    if (
        download_etcd.changed
        or not etcd_link
        or not host.fact.file(etcd_link['link_target'])
    ):
        files.link(
            {'Symlink etcd to /usr/bin'},
            '/usr/local/bin/etcd',  # link
            '/usr/local/etcd/{0}/etcd'.format(version_name),  # target
        )

    etcdctl_link = host.fact.link('/usr/local/bin/etcdctl')
    if (
        download_etcd.changed
        or not etcdctl_link
        or not host.fact.file(etcdctl_link['link_target'])
    ):
        files.link(
            {'Symlink etcdctl to /usr/local/bin'},
            '/usr/local/bin/etcdctl',
            '/usr/local/etcd/{0}/etcdctl'.format(version_name),
        )

    # Setup etcd init
    files.template(
        {'Upload the etcd systemd unit file'},
        _get_template_path('etcd.service.j2'),
        '/etc/systemd/system/etcd.service',
    )

    # Configure etcd
    files.template(
        {'Upload the etcd env file'},
        _get_template_path('etcd.conf.j2'),
        '{{ host.data.etcd_env_file }}',
        # Cluster (peers)
        cluster_node_urls=_get_cluster_node_urls(),
        # Peer
        advertise_peer_urls=_get_urls(host, 'peer'),
        listen_peer_urls=_get_urls(host, 'peer'),
        # Client
        advertise_client_urls=_get_urls(host, 'client'),
        listen_client_urls=_get_urls(host, 'client'),
    )

    # Start (/enable) the etcd service
    op_name = 'Ensure etcd service is running'
    if enable_service:
        op_name = '{0} and enabled'.format(op_name)

    init.systemd(
        {op_name},
        'etcd',
        enabled=enable_service,
    )
