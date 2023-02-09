# © Copyright Databand.ai, an IBM Company 2022
import json

import pytest

from dbnd_datastage_monitor.adapter.datastage_adapter import DataStageAdapter
from dbnd_datastage_monitor.data.datastage_config_data import DataStageServerConfig
from dbnd_datastage_monitor.datastage_client.datastage_assets_client import (
    ConcurrentRunsGetter,
)
from freezegun import freeze_time

from dbnd import relative_path
from dbnd._core.utils.uid_utils import get_uuid

from .test_datastage_assets_client import init_mock_client


@pytest.fixture
def mock_datastage_config() -> DataStageServerConfig:
    yield DataStageServerConfig(
        uid=get_uuid(),
        source_name="test_syncer",
        source_type="integration",
        tracking_source_uid=get_uuid(),
        sync_interval=10,
        number_of_fetching_threads=2,
        project_ids=["1", "2"],
        fetching_interval_in_minutes=30,
    )


@pytest.fixture
def datastage_adapter(mock_datastage_config: DataStageServerConfig) -> DataStageAdapter:
    yield DataStageAdapter(
        datastage_assets_client=ConcurrentRunsGetter(client=init_mock_client()),
        config=mock_datastage_config,
    )


class TestDataStageAdapter:
    @freeze_time("2022-11-16T15:30:11Z")
    def test_datastage_adapter_get_last_cursor(
        self, datastage_adapter: DataStageAdapter
    ):
        assert datastage_adapter.get_last_cursor() == "2022-11-16T15:30:11Z"

    @freeze_time("2022-07-28T13:25:19Z")
    def test_datastage_adapter_get_data(self, datastage_adapter: DataStageAdapter):
        adapter_data_result = datastage_adapter.get_new_data(
            cursor=datastage_adapter.get_last_cursor(), batch_size=100, next_page=None
        )
        expected_data = json.load(
            open(relative_path(__file__, "mocks/fetcher_response.json"))
        )
        assert adapter_data_result.data == expected_data
        assert datastage_adapter.get_last_cursor() == "2022-07-28T13:25:19Z"

    @freeze_time("2023-02-13T13:53:20Z")
    def test_datastage_adapter_get_data_out_of_range(
        self, datastage_adapter: DataStageAdapter
    ):
        adapter_data_result = datastage_adapter.get_new_data(
            cursor=datastage_adapter.get_last_cursor(), batch_size=100, next_page=None
        )
        assert adapter_data_result.data is None
        assert datastage_adapter.get_last_cursor() == "2023-02-13T13:53:20Z"

    def test_datastage_adapter_update_data(self, datastage_adapter: DataStageAdapter):
        data_to_update = [
            "https://api.dataplatform.cloud.ibm.com/v2/assets/175a521f-6525-4d71-85e2-22544f8267a6?project_id=0ca4775d-860c-44f2-92ba-c7c8cfc0dd45"
        ]
        update_data = datastage_adapter.get_update_data(data_to_update)
        expected_data = json.load(
            open(relative_path(__file__, "mocks/fetcher_response.json"))
        )
        assert expected_data == update_data
