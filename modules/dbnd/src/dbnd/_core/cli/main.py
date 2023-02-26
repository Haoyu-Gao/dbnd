#!/usr/bin/env python
# -*- coding: utf-8 -*-

# © Copyright Databand.ai, an IBM Company 2022

import logging
import shlex
import subprocess
import sys

from functools import partial

import six

from dbnd._core.cli.cmd_deprecated import add_deprecated_commands
from dbnd._core.cli.cmd_show import show_configs
from dbnd._core.cli.cmd_tracker import tracker
from dbnd._core.context.bootstrap import dbnd_bootstrap
from dbnd._core.failures import dbnd_handle_errors
from dbnd._core.log.config import configure_basic_logging
from dbnd._core.plugin.dbnd_plugins import register_dbnd_cli_commands
from dbnd._core.utils.platform import windows_compatible_mode
from dbnd._vendor import click
from dbnd._vendor.click_didyoumean import DYMGroup
from dbnd.cli.cmd_airflow_sync import airflow_sync
from dbnd.cli.cmd_alerts import alerts
from dbnd.cli.cmd_scheduler_management import schedule
from dbnd.orchestration.cli.cmd_execute import execute
from dbnd.orchestration.cli.cmd_heartbeat import send_heartbeat
from dbnd.orchestration.cli.cmd_project import project_init
from dbnd.orchestration.cli.cmd_run import cmd_run
from dbnd.orchestration.cli.cmd_show import show_tasks
from dbnd.orchestration.cli.cmd_utils import collect_logs, ipython


logger = logging.getLogger(__name__)


@click.group(cls=DYMGroup)
def cli():
    dbnd_bootstrap(dbnd_entrypoint=True)


# project
cli.add_command(project_init)

# run
cli.add_command(cmd_run)
cli.add_command(execute)
cli.add_command(ipython)

# show
cli.add_command(show_configs)
cli.add_command(show_tasks)

# tracker
cli.add_command(tracker)

# heartbeat sender
cli.add_command(send_heartbeat)

# clients for the web-api
cli.add_command(alerts)
cli.add_command(airflow_sync)
cli.add_command(schedule)

# error reporting
cli.add_command(collect_logs)

add_deprecated_commands(cli)


@dbnd_handle_errors(exit_on_error=False)
def dbnd_cmd(command, args):
    """
    Invokes the passed dbnd command with CLI args emulation.

    Args:
        command (str): the command to be invoked
        args (Union[list, str]): list with CLI args to be emulated (if str is passed, it will be split)

    Returns:
        str: result of command execution
    """
    dbnd_bootstrap()

    assert command in cli.commands
    if isinstance(args, six.string_types) or isinstance(args, six.text_type):
        args = shlex.split(args, posix=not windows_compatible_mode)
    current_argv = sys.argv
    logger.info("Running dbnd run: %s", subprocess.list2cmdline(args))
    try:
        sys.argv = [sys.executable, "-m", "databand", command] + args
        return cli.commands[command](args=args, standalone_mode=False)
    finally:
        sys.argv = current_argv


dbnd_run_cmd = partial(dbnd_cmd, "run")


def dbnd_run_cmd_main(task, env=None, args=None):
    """A wrapper for dbnd_cmd_run with error handling."""
    from dbnd import Task

    if isinstance(task, Task):
        task_str = task.get_full_task_family()
    else:
        task_str = task

    try:
        cmd_args = [task_str]
        if env is not None:
            cmd_args = cmd_args + ["--env", env]
        if args is not None:
            cmd_args = cmd_args + args
        return dbnd_cmd("run", cmd_args)
    except KeyboardInterrupt:
        logger.error("Keyboard interrupt, exiting...")
        sys.exit(1)
    except Exception as ex:
        from dbnd._core.failures import get_databand_error_message

        msg, code = get_databand_error_message(ex=ex, args=sys.argv[1:])
        logger.error("dbnd cmd run failed with error: {}".format(msg))
        if code is not None:
            sys.exit(code)


def _register_legacy_airflow_monitor_commands(cli):
    try:
        from airflow_monitor.multiserver.cmd_liveness_probe import (
            airflow_monitor_v2_alive,
        )
        from airflow_monitor.multiserver.cmd_multiserver import airflow_monitor_v2
    except ImportError:
        return

    cli.add_command(airflow_monitor_v2_alive)
    cli.add_command(airflow_monitor_v2)
    return cli


def main():
    """Script's main function and start point."""
    configure_basic_logging(None)

    dbnd_bootstrap()

    register_dbnd_cli_commands(cli)

    _register_legacy_airflow_monitor_commands(cli)
    try:
        return cli(prog_name="dbnd")

    except KeyboardInterrupt:
        sys.exit(1)

    except Exception as ex:
        from dbnd._core.failures import get_databand_error_message

        msg, code = get_databand_error_message(ex=ex, args=sys.argv[1:])
        logger.error(msg)
        if code is not None:
            sys.exit(code)

    except SystemExit as ex:
        if ex.code == 0:
            # databricks can't handle for a reason exit with an exit code.
            exit()
        else:
            sys.exit(ex.code)


if __name__ == "__main__":
    main()
