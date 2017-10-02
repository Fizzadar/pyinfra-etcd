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
def install_etcd(state, host):
    if not host.data.etcd_version:
        raise DeployError(
            'No etcd_version set for this host, refusing to install etcd!',
        )

    server.user(
        state, host,
        {'Create the etcd user'},
        'etcd',
        shell='/sbin/nologin',
    )

    files.directory(
        state, host,
        {'Ensure the etcd data directory exists'},
        '{{ host.data.etcd_data_dir }}',
        user='etcd',
        group='etcd',
    )

    files.directory(
        state, host,
        {'Ensure {0} exists'.format(host.data.etcd_install_dir)},
        host.data.etcd_install_dir,
        user='etcd',
        group='etcd',
    )

    # Work out the filename
    host.data.etcd_version_name = (
        'etcd-{0}-linux-'
        'amd64' if host.fact.arch == 'x86_64' else host.fact.arch
    ).format(host.data.etcd_version)

    # Work out the download URL
    download_url = (
        '{{ host.data.etcd_download_base_url }}/'
        '{{ host.data.etcd_version }}/'
        '{{ host.data.etcd_version_name }}.tar.gz'
    )

    host.data.etcd_temp_filename = state.get_temp_filename(
        'etcd-{0}'.format(host.data.etcd_version),
    )

    download_etcd = files.download(
        state, host,
        {'Download etcd'},
        download_url,
        '{{ host.data.etcd_temp_filename }}',
    )

    # If we downloaded etcd, extract it!
    if download_etcd.changed:
        server.shell(
            state, host,
            {'Extract etcd'},
            'tar -xzf {{ host.data.etcd_temp_filename }} -C /usr/local/etcd',
        )

    files.link(
        state, host,
        {'Symlink etcd to /usr/bin'},
        '{{ host.data.etcd_bin_dir }}/etcd',  # link
        '{{ host.data.etcd_install_dir }}/{{ host.data.etcd_version_name }}/etcd',
    )

    files.link(
        state, host,
        {'Symlink etcdctl to {0}'.format(host.data.etcd_bin_dir)},
        '{{ host.data.etcd_bin_dir }}/etcdctl',
        '{{ host.data.etcd_install_dir }}/{{ host.data.etcd_version_name }}/etcdctl',
    )


@deploy('Configure etcd', data_defaults=DEFAULTS)
def configure_etcd(state, host, enable_service=True):
    # Setup etcd init
    generate_service = files.template(
        state, host,
        {'Upload the etcd systemd unit file'},
        _get_template_path('etcd.service.j2'),
        '/etc/systemd/system/etcd.service',
    )

    # Configure etcd
    files.template(
        state, host,
        {'Upload the etcd env file'},
        _get_template_path('etcd.conf.j2'),
        '{{ host.data.etcd_env_file }}',
        # Cluster (peers)
        cluster_node_urls=_get_cluster_node_urls(),
        get_urls=_get_urls,
    )

    # Start (/enable) the etcd service
    op_name = 'Ensure etcd service is running'
    if enable_service:
        op_name = '{0} and enabled'.format(op_name)

    init.systemd(
        state, host,
        {op_name},
        'etcd',
        enabled=enable_service,
        daemon_reload=generate_service.changed,
    )


def deploy_etcd(enable_service=True):
    install_etcd()
    configure_etcd(enable_service=enable_service)
