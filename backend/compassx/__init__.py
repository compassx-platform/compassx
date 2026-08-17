"""CompassX Platform Abstraction Layer.

Deployment-independent subsystems:

- Service Registry  — resolves service endpoints per deployment mode
- Runtime Manager   — manages user execution runtimes (notebooks, jobs, ...)
- Resource Manager  — provisions infrastructure via drivers (local/docker/k8s)
- Platform Manager  — platform lifecycle (compassx up/down/status) via launchers
"""
