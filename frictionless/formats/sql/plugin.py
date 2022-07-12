from ...plugin import Plugin
from .control import SqlControl
from .parser import SqlParser
from .storage import SqlStorage
from . import settings


# NOTE:
# Can we improve `engline.dialect.name.startswith()` checks?


class SqlPlugin(Plugin):
    """Plugin for SQL"""

    # Hooks

    def create_control(self, descriptor):
        if descriptor.get("type") == "sql":
            return SqlControl.from_descriptor(descriptor)

    def create_parser(self, resource):
        if resource.format == "sql":
            return SqlParser(resource)

    def create_storage(self, name, source, **options):
        if name == "sql":
            return SqlStorage(source, **options)

    def detect_resource(self, resource):
        if resource.scheme:
            for prefix in settings.SCHEME_PREFIXES:
                if resource.scheme.startswith(prefix):
                    resource.type = "table"
                    resource.scheme = ""
                    resource.format = "sql"
