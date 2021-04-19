import logging

from typing import Any, Dict

from dbnd._core.current import in_tracking_run, is_orchestration_run
from dbnd._core.errors.base import TrackerPanicError
from dbnd._core.errors.errors_utils import log_exception
from dbnd._core.tracking.backends import TrackingStore, TrackingStoreThroughChannel
from dbnd._core.tracking.backends.abstract_tracking_store import is_state_call


MAX_RETRIES = 2

logger = logging.getLogger(__name__)


def try_run_handler(tries, store, handler_name, kwargs, verbose=False):
    # type: (int, TrackingStore, str, Dict[str, Any],bool) -> Any
    """
    Locate the handler function to run and will try to run it multiple times.
    If fails all the times -> raise the last error.

    @param tries: maximum amount of retries, positive integer.
    @param store: the store to run its handler
    @param handler_name: the name of the handler to run
    @param kwargs: the input for the handler
    @param verbose: should we log verbosely
    @return: The result of the handler if succeeded, otherwise raise the last error
    """
    try_num = 1
    handler = getattr(store, handler_name)

    while True:
        try:
            return handler(**kwargs)

        except Exception as ex:
            log_exception(
                "Try %s out of %s: Failed to store tracking information from %s at %s"
                % (try_num, tries, handler_name, str(store)),
                ex,
                non_critical=True,
                verbose=verbose,
            )

            if try_num == tries:
                # raise on the last try
                raise

            try_num += 1


class CompositeTrackingStore(TrackingStore):
    def __init__(
        self,
        tracking_stores,
        max_retires,
        raise_on_error=True,
        remove_failed_store=False,
    ):
        if not tracking_stores:
            logger.warning("You are running without any tracking store configured.")

        self._stores = tracking_stores
        self._raise_on_error = raise_on_error
        self._remove_failed_store = remove_failed_store
        self._max_retries = max_retires

    def _invoke(self, name, kwargs):
        res = None
        failed_stores = []

        for store in self._stores:
            tries = self._max_retries if is_state_call(name) else 1

            try:
                res = try_run_handler(
                    tries, store, name, kwargs, verbose=is_orchestration_run()
                )
            except Exception as e:
                if self._remove_failed_store or (
                    in_tracking_run() and is_state_call(name)
                ):
                    failed_stores.append(store)

                if isinstance(e, TrackerPanicError) and self._raise_on_error:
                    raise

        if failed_stores:
            for store in failed_stores:
                logger.warning(
                    "Removing store %s from stores list due to failure" % (str(store),)
                )
                self._stores.remove(store)

            if not self._stores:
                logger.warning("You are running without any tracking store configured.")

        return res

    # this is a function that used for disabling Tracking api on spark inline tasks.
    def disable_tracking_api(self):
        filtered_stores = []

        for store in self._stores:
            if isinstance(store, TrackingStoreThroughChannel):
                continue
            filtered_stores.append(store)
        self._stores = filtered_stores

    def init_scheduled_job(self, **kwargs):
        return self._invoke(CompositeTrackingStore.init_scheduled_job.__name__, kwargs)

    def init_run(self, **kwargs):
        return self._invoke(CompositeTrackingStore.init_run.__name__, kwargs)

    def init_run_from_args(self, **kwargs):
        return self._invoke(CompositeTrackingStore.init_run_from_args.__name__, kwargs)

    def set_run_state(self, **kwargs):
        return self._invoke(CompositeTrackingStore.set_run_state.__name__, kwargs)

    def set_task_reused(self, **kwargs):
        return self._invoke(CompositeTrackingStore.set_task_reused.__name__, kwargs)

    def set_task_run_state(self, **kwargs):
        return self._invoke(CompositeTrackingStore.set_task_run_state.__name__, kwargs)

    def set_task_run_states(self, **kwargs):
        return self._invoke(CompositeTrackingStore.set_task_run_states.__name__, kwargs)

    def set_unfinished_tasks_state(self, **kwargs):
        return self._invoke(
            CompositeTrackingStore.set_unfinished_tasks_state.__name__, kwargs
        )

    def save_task_run_log(self, **kwargs):
        return self._invoke(CompositeTrackingStore.save_task_run_log.__name__, kwargs)

    def save_external_links(self, **kwargs):
        return self._invoke(CompositeTrackingStore.save_external_links.__name__, kwargs)

    def log_target(self, **kwargs):
        return self._invoke(CompositeTrackingStore.log_target.__name__, kwargs)

    def log_targets(self, **kwargs):
        return self._invoke(CompositeTrackingStore.log_targets.__name__, kwargs)

    def log_histograms(self, **kwargs):
        return self._invoke(CompositeTrackingStore.log_histograms.__name__, kwargs)

    def log_metrics(self, **kwargs):
        return self._invoke(CompositeTrackingStore.log_metrics.__name__, kwargs)

    def log_artifact(self, **kwargs):
        return self._invoke(CompositeTrackingStore.log_artifact.__name__, kwargs)

    def close(self):
        pass

    def add_task_runs(self, **kwargs):
        return self._invoke(CompositeTrackingStore.add_task_runs.__name__, kwargs)

    def heartbeat(self, **kwargs):
        return self._invoke(CompositeTrackingStore.heartbeat.__name__, kwargs)

    def save_airflow_task_infos(self, **kwargs):
        return self._invoke(
            CompositeTrackingStore.save_airflow_task_infos.__name__, kwargs
        )

    def update_task_run_attempts(self, **kwargs):
        return self._invoke(
            CompositeTrackingStore.update_task_run_attempts.__name__, kwargs
        )

    def is_ready(self, **kwargs):
        return all(store.is_ready() for store in self._stores)

    def save_airflow_monitor_data(self, **kwargs):
        return self._invoke(
            CompositeTrackingStore.save_airflow_monitor_data.__name__, kwargs
        )
