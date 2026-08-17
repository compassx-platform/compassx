from .local import LocalDriver

__all__ = ["LocalDriver", "get_docker_driver_cls", "get_kubernetes_driver_cls"]


def get_docker_driver_cls():
    """Import DockerDriver lazily so the docker SDK is optional."""
    from .docker import DockerDriver

    return DockerDriver


def get_kubernetes_driver_cls():
    """Import KubernetesDriver lazily so the kubernetes lib is optional."""
    from .kubernetes import KubernetesDriver

    return KubernetesDriver
