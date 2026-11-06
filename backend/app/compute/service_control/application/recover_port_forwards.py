class RecoverPortForwards:
    async def execute(self):
        return {
            "enabled": False,
            "message": "Port-forwards are managed by the compassx CLI. Run: compassx up",
        }


def recover_port_forwards():
    return RecoverPortForwards().execute()
