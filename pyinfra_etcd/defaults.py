# pyinfra etcd
# File: pyinfra_etcd/defaults.py
# Desc: default data for pyinfra etcd

DEFAULTS = {
    # Install
    'etcd_version': None,
    'etcd_download_base_url': 'https://github.com/coreos/etcd/releases/download',
    'etcd_install_dir': '/usr/local/etcd',
    'etcd_bin_dir': '/usr/local/bin',

    # Node config
    'etcd_user': 'etcd',
    'etcd_env_file': '/etc/default/etcd',
    'etcd_data_dir': '/var/lib/etcd',
    'etcd_peer_port': 2380,
    'etcd_client_port': 2379,

    # Network interfaces
    'etcd_interface': None,
    'etcd_interface_type': None,
    # Make client/peer run on different interfaces (default to above)
    'etcd_client_interface': None,
    'etcd_client_interface_type': None,
    'etcd_peer_interface': None,
    'etcd_peer_interface_type': None,

    # Always listen on localhost irrespective of interface?
    'etcd_listen_localhost': True,
    'etcd_client_listen_localhost': True,
    'etcd_peer_listen_localhost': True,

    # Cluster config
    'etcd_initial_cluster_state': 'new',
    'etcd_initial_cluster_token': 'etcd-cluster',
}
