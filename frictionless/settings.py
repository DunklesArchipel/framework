# type: ignore
from __future__ import annotations
import os
import json
import gzip
import zipfile


# Helpers


def read_asset(*paths, encoding="utf-8"):
    dirname = os.path.dirname(__file__)
    with open(os.path.join(dirname, "assets", *paths), encoding=encoding) as file:
        return file.read().strip()


# General


UNDEFINED = object()
VERSION = read_asset("VERSION")
COMPRESSION_FORMATS = ["zip", "gz"]
PACKAGE_PROFILE = json.loads(read_asset("profiles", "package.json"))
SCHEMA_PROFILE = json.loads(read_asset("profiles", "schema.json"))
GEOJSON_PROFILE = json.loads(read_asset("profiles", "geojson", "general.json"))
TOPOJSON_PROFILE = json.loads(read_asset("profiles", "geojson", "topojson.json"))


# Defaults


DEFAULT_STANDARDS_VERSION = "v2"
DEFAULT_TYPE = "file"
DEFAULT_SCHEME = "file"
DEFAULT_FORMAT = "csv"
DEFAULT_HASHING = "md5"
DEFAULT_ENCODING = "utf-8"
DEFAULT_INNERPATH = ""
DEFAULT_PACKAGE_INNERPATH = "datapackage.json"
DEFAULT_COMPRESSION = ""
DEFAULT_BASEPATH = ""
DEFAULT_TRUSTED = True
DEFAULT_ONERROR = "ignore"
DEFAULT_HEADER = True
DEFAULT_HEADER_ROWS = [1]
DEFAULT_HEADER_JOIN = " "
DEFAULT_HEADER_CASE = True
DEFAULT_FLOAT_NUMBERS = False
DEFAULT_MISSING_VALUES = [""]
DEFAULT_LIMIT_ERRORS = 1000
DEFAULT_LIMIT_MEMORY = 1000
DEFAULT_BUFFER_SIZE = 10000
DEFAULT_SAMPLE_SIZE = 100
DEFAULT_ENCODING_CONFIDENCE = 0.5
DEFAULT_FIELD_CONFIDENCE = 0.9
DEFAULT_PACKAGE_PROFILE = "data-package"
DEFAULT_RESOURCE_PROFILE = "data-resource"
DEFAULT_TABULAR_RESOURCE_PROFILE = "tabular-data-resource"
DEFAULT_FIELD_TYPE = "any"
DEFAULT_FIELD_FORMAT = "default"
DEFAULT_TRUE_VALUES = ["true", "True", "TRUE", "1"]
DEFAULT_FALSE_VALUES = ["false", "False", "FALSE", "0"]
DEFAULT_DATETIME_PATTERN = "%Y-%m-%dT%H:%M:%S%z"
DEFAULT_DATE_PATTERN = "%Y-%m-%d"
DEFAULT_TIME_PATTERN = "%H:%M:%S%z"
DEFAULT_BARE_NUMBER = True
DEFAULT_FLOAT_NUMBER = False
DEFAULT_GROUP_CHAR = ""
DEFAULT_DECIMAL_CHAR = "."
DEFAULT_SERVER_PORT = 8000
DEFAULT_FIELD_CANDIDATES = [
    {"type": "yearmonth"},
    {"type": "geopoint"},
    {"type": "duration"},
    {"type": "geojson"},
    {"type": "object"},
    {"type": "array"},
    {"type": "datetime"},
    {"type": "time"},
    {"type": "date"},
    {"type": "integer"},
    {"type": "number"},
    {"type": "boolean"},
    {"type": "year"},
    {"type": "string"},
]

# Entities

ENTITY_TRAITS = {
    "package": ["resources"],
    "resource": ["path", "data"],
    "dialect": ["controls"],
    "schema": ["fields"],
    "checklist": ["checks"],
    "pipeline": ["steps"],
    "report": ["erorrs"],
    "inquiry": ["tasks"],
    "detector": ["bufferSize", "sampleSize"],
}

# Backports

# TODO: drop for v5
# It can be removed after dropping support for Python 3.6 and Python 3.7
COMPRESSION_EXCEPTIONS = (
    (zipfile.BadZipFile, gzip.BadGzipFile)
    if hasattr(gzip, "BadGzipFile")
    else (zipfile.BadZipFile)
)
