from airflow.models import DagModel
from airflow.utils.db import provide_session

from dbnd_airflow_export.dag_processing import (
    get_current_dag_model,
    get_dags,
    load_dags_models,
)
from dbnd_airflow_export.models import (
    AirflowNewDagRun,
    DagRunsStatesData,
    FullRunsData,
    LastSeenData,
    NewRunsData,
)
from dbnd_airflow_export.queries import (
    find_all_logs_grouped_by_runs,
    find_full_dag_runs,
    find_max_dag_run_id,
    find_max_log_run_id,
    find_new_dag_runs,
)


@provide_session
def get_last_seen_values(session=None):
    max_dag_run_id = find_max_dag_run_id(session)
    max_log_id = find_max_log_run_id(session)

    return LastSeenData(
        last_seen_dag_run_id=max_dag_run_id, last_seen_log_id=max_log_id
    )


@provide_session
def get_new_dag_runs(
    last_seen_dag_run_id, last_seen_log_id, extra_dag_runs_ids, session=None
):
    max_dag_run_id = find_max_dag_run_id(session)
    max_log_id = find_max_log_run_id(session)

    if last_seen_dag_run_id is None:
        last_seen_dag_run_id = max_dag_run_id

    if last_seen_log_id is None:
        last_seen_log_id = max_log_id

    logs = find_all_logs_grouped_by_runs(last_seen_log_id, session)
    logs_dict = {(log.dag_id, log.execution_date): log for log in logs}

    dag_runs = find_new_dag_runs(
        last_seen_dag_run_id, extra_dag_runs_ids, logs_dict.keys(), session
    )

    new_dag_runs = []
    for dag_run in dag_runs:
        log = logs_dict.get((dag_run.dag_id, dag_run.execution_date), None)

        if log is None:
            events = []
        elif isinstance(log.events, str):  # mysql, sqlite
            events = log.events.split(",")
        else:  # postgres
            events = log.events

        new_dag_run = AirflowNewDagRun(
            id=dag_run.id,
            dag_id=dag_run.dag_id,
            execution_date=dag_run.execution_date,
            state=dag_run.state,
            is_paused=dag_run.is_paused,
            has_updated_task_instances=(dag_run.dag_id, dag_run.execution_date)
            in logs_dict,
            events=events,
            max_log_id=log.id if log else None,
        )
        new_dag_runs.append(new_dag_run)

    new_runs = NewRunsData(
        new_dag_runs=new_dag_runs,
        last_seen_dag_run_id=max_dag_run_id,
        last_seen_log_id=max_log_id,
    )
    return new_runs


@provide_session
def get_full_dag_runs(dag_run_ids, airflow_dagbag=None, session=None):
    if airflow_dagbag:
        dagbag = airflow_dagbag
    else:
        from airflow import settings

        if settings.RBAC:
            from airflow.www_rbac.views import dagbag
        else:
            from airflow.www.views import dagbag

    old_get_current_dag = DagModel.get_current
    try:
        DagModel.get_current = get_current_dag_model
        load_dags_models(session)
        task_instances, dag_runs = find_full_dag_runs(dag_run_ids, session)
        dag_ids = set(run.dag_id for run in dag_runs)
        dags = get_dags(dagbag, True, dag_ids, False)
        full_runs = FullRunsData(
            task_instances=task_instances, dag_runs=dag_runs, dags=dags
        )
        return full_runs
    finally:
        DagModel.get_current = old_get_current_dag


@provide_session
def get_dag_runs_states_data(dag_run_ids, session=None):
    task_instances, dag_runs = find_full_dag_runs(dag_run_ids, session)
    dag_runs_states_data = DagRunsStatesData(
        task_instances=task_instances, dag_runs=dag_runs
    )
    return dag_runs_states_data