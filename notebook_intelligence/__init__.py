# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>
 
try:
    from ._version import __version__
except ImportError:
    # Fallback when using the package in dev mode without installing
    # in editable mode with pip. It is highly recommended to install
    # the package from a stable release or in editable mode: https://pip.pypa.io/en/stable/topics/local-project-installs/#editable-installs
    import warnings
    warnings.warn("Importing 'notebook_intelligence' outside a proper installation.")
    __version__ = "dev"
from .handlers import initialize_extensions, setup_handlers
from .extension import *

def _jupyter_labextension_paths():
    return [{
        "src": "labextension",
        "dest": "@mbektas/notebook-intelligence"
    }]


def _jupyter_server_extension_points():
    return [{
        "module": "notebook_intelligence"
    }]


def _load_jupyter_server_extension(server_app):
    """Registers the API handler to receive HTTP requests from the frontend extension.

    Parameters
    ----------
    server_app: jupyterlab.labapp.LabApp
        JupyterLab application instance
    """
    initialize_extensions()
    setup_handlers(server_app.web_app)
    name = "notebook_intelligence"
    server_app.log.info(f"Registered {name} server extension")
