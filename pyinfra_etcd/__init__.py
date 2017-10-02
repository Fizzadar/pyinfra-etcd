# pyinfra etcd
# File: pyinfra_etcd/__init__.py
# Desc: export deploys and install/configure helper function

from .etcd import configure_etcd, install_etcd


def deploy_etcd(enable_service=True):
    install_etcd()
    configure_etcd(enable_service=enable_service)
