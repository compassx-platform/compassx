from app.monitoring.schemas import Resource


class ListResources:
    def __init__(self, resource_manager):
        self.resource_manager = resource_manager

    def execute(self, kind: str | None = None) -> list[Resource]:
        return [
            Resource.model_validate(item, from_attributes=True)
            for item in self.resource_manager.resources(kind)
        ]


def list_resources(resource_manager, kind: str | None = None) -> list[Resource]:
    return ListResources(resource_manager).execute(kind)
