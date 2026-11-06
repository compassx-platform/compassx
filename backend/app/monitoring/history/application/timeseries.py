from app.monitoring.schemas import TimeseriesResponse


class ReadTimeseries:
    def __init__(self, resource_manager):
        self.resource_manager = resource_manager

    def execute(
        self, resource_type: str, resource_id: str, metric: str, start: int, end: int, step: int
    ) -> TimeseriesResponse:
        observed = self.resource_manager.timeseries(
            resource_type, resource_id, metric, start, end, step
        )
        return TimeseriesResponse.model_validate(observed, from_attributes=True)


def read_timeseries(resource_manager, resource_type: str, resource_id: str, metric: str, start: int, end: int, step: int) -> TimeseriesResponse:
    return ReadTimeseries(resource_manager).execute(resource_type, resource_id, metric, start, end, step)
