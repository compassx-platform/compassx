class PortForwardStatus:
    def execute(self):
        return {
            "enabled": False,
            "message": "Port-forwards are managed by the compassx CLI. Run: compassx status",
            "forwards": [],
        }


def port_forward_status():
    return PortForwardStatus().execute()
