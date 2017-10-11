# pyinfra etcd
# File: pyinfra_etcd/__init__.py
# Desc: export deploys and install/configure helper function

from pyinfra.api import deploy

from .etcd import configure_etcd, install_etcd


@deploy('Deploy etcd')
def deploy_etcd(state, host, enable_service=True):
    install_etcd(state, host)
    configure_etcd(state, host, enable_service=enable_service)
