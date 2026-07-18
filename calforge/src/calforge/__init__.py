"""CalForge — professional AI-assisted ECU calibration workbench.

The package is a modular monolith organised in strict layers:

- ``calforge.core``      application kernel (config, logging, events, DI, plugins)
- ``calforge.data``      persistence (SQLAlchemy models, migrations, blob store)
- ``calforge.services``  application services exposed to the UI and plugins
- ``calforge.analysis``  binary analysis engines (diff, identification, statistics)
- ``calforge.formats``   ECU file format identifiers (plugin-extensible)
- ``calforge.ui``        PySide6 desktop interface

Lower layers never import from higher layers. The UI only talks to
``calforge.services`` and communicates back through the event bus.
"""

__version__ = "0.2.0"
APP_NAME = "CalForge"
