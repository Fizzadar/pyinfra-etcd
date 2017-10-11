# pyinfra etcd
# File: pyinfra_etcd/etcd.py
# Desc: installs/configures etcd as a systemd service using pyinfra

from pyinfra.api import deploy, DeployError
from pyinfra.modules import files, init, server

from .defaults import DEFAULTS
from .util import get_cluster_node_urls, get_template_path, get_urls


@deploy('Install etcd', data_defaults=DEFAULTS)
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
        user=host.data.etcd_user,
        group=host.data.etcd_user,
    )

    files.directory(
        state, host,
        {'Ensure the etcd install directory exists'},
        host.data.etcd_install_dir,
        user=host.data.etcd_user,
        group=host.data.etcd_user,
    )

    # Work out the filename
    host.data.etcd_version_name = (
        'etcd-{0}-linux-'
        'amd64' if host.fact.arch == 'x86_64' else host.fact.arch
    ).format(host.data.etcd_version)

    host.data.etcd_temp_filename = state.get_temp_filename(
        'etcd-{0}'.format(host.data.etcd_version),
    )

    download_etcd = files.download(
        state, host,
        {'Download etcd'},
        (
            '{{ host.data.etcd_download_base_url }}/'
            '{{ host.data.etcd_version }}/'
            '{{ host.data.etcd_version_name }}.tar.gz'
        ),
        '{{ host.data.etcd_temp_filename }}',
    )

    # If we downloaded etcd, extract it!
    server.shell(
        state, host,
        {'Extract etcd'},
        'tar -xzf {{ host.data.etcd_temp_filename }} -C {{ host.data.etcd_install_dir }}',
        when=download_etcd.changed,
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
        get_template_path('etcd.service.j2'),
        '/etc/systemd/system/etcd.service',
    )

    # Configure etcd
    files.template(
        state, host,
        {'Upload the etcd env file'},
        get_template_path('etcd.conf.j2'),
        '{{ host.data.etcd_env_file }}',
        # Cluster (peers)
        cluster_node_urls=get_cluster_node_urls(state.inventory),
        get_urls=get_urls,
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
