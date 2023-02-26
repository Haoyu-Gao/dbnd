# © Copyright Databand.ai, an IBM Company 2022

import importlib
import logging

from dbnd._core.configuration import get_dbnd_project_config
from dbnd._core.errors import friendly_error
from dbnd._core.plugin import dbnd_plugin_spec
from dbnd._core.utils.basics.load_python_module import _load_module
from dbnd._core.utils.seven import fix_sys_path_str, import_errors
from dbnd._vendor import pluggy


logger = logging.getLogger(__name__)

hookimpl = pluggy.HookimplMarker("dbnd")
pm = pluggy.PluginManager("dbnd")
pm.add_hookspecs(dbnd_plugin_spec)


# all other modules
def is_plugin_enabled(module, module_import=None):
    if pm.has_plugin(module):
        return True

    if module_import:
        try:
            importlib.import_module(module_import)
            return True
        except import_errors:
            pass
    if "-" in module:
        # Workaround for manually loaded plugins (contain `_` instead of `-`)
        # Occurs when 'disable_pluggy_entrypoint_loading' is turned on in spark-config. All plugins are loaded
        # manually (spark_ctrl.py:107), so we must fix `plugin` syntax ('-') to python module syntax ('_')
        return is_plugin_enabled(module.replace("-", "_"), module_import)
    return False


def assert_plugin_enabled(module, reason=None, module_import=None):
    if not is_plugin_enabled(module, module_import=module_import):
        raise friendly_error.config.missing_module(module, reason)
    return True


_dbnd_plugins_registered = False


def register_dbnd_plugins():
    if get_dbnd_project_config().is_no_plugins:
        return

    global _dbnd_plugins_registered
    if _dbnd_plugins_registered:
        return
    _dbnd_plugins_registered = True

    fix_sys_path_str()
    if not get_dbnd_project_config().disable_pluggy_entrypoint_loading:
        pm.load_setuptools_entrypoints("dbnd")
        pm.check_pending()


def register_dbnd_user_plugins(user_plugin_modules):
    for plugin_module in user_plugin_modules:
        module = _load_module(plugin_module, "plugin:%s" % plugin_module)
        pm.register(module)

        base_msg = "Plugin %s" % plugin_module
        if getattr(module, "__version__", None):
            base_msg += " v%s" % module.__version__

        logger.info(base_msg + " loaded...")


def register_dbnd_cli_commands(cli):
    # adding all plugins cli commands
    for commands in pm.hook.dbnd_get_commands():
        for command in commands:
            cli.add_command(command)
