from __future__ import annotations
import os
import json
import petl
import warnings
from pathlib import Path
from collections.abc import Mapping
from typing import TYPE_CHECKING, Optional, Union, List, Any
from ..exception import FrictionlessException
from ..table import Header, Lookup, Row
from ..dialect import Dialect, Control
from ..checklist import Checklist
from ..detector import Detector
from ..metadata import Metadata
from ..pipeline import Pipeline
from ..schema import Schema
from ..system import system
from .. import settings
from .. import helpers
from .. import errors
from .. import fields
from . import methods


if TYPE_CHECKING:
    from .loader import Loader
    from .parser import Parser
    from ..package import Package
    from ..interfaces import IDescriptorSource, IOnerror, IBuffer, ISample, IFragment
    from ..interfaces import ILabels, IByteStream, ITextStream, ICellStream, IRowStream


class Resource(Metadata):
    """Resource representation.

    This class is one of the cornerstones of of Frictionless framework.
    It loads a data source, and allows you to stream its parsed contents.
    At the same time, it's a metadata class data description.

    ```python
    with Resource("data/table.csv") as resource:
        resource.header == ["id", "name"]
        resource.read_rows() == [
            {'id': 1, 'name': 'english'},
            {'id': 2, 'name': '中国人'},
        ]
    ```

    """

    analyze = methods.analyze
    describe = methods.describe
    extract = methods.extract
    validate = methods.validate
    transform = methods.transform

    def __init__(
        self,
        source: Optional[Any] = None,
        *,
        # Standard
        name: Optional[str] = None,
        type: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        homepage: Optional[str] = None,
        profiles: List[str] = [],
        licenses: List[dict] = [],
        sources: List[dict] = [],
        path: Optional[str] = None,
        data: Optional[Any] = None,
        scheme: Optional[str] = None,
        format: Optional[str] = None,
        hashing: Optional[str] = None,
        encoding: Optional[str] = None,
        mediatype: Optional[str] = None,
        compression: Optional[str] = None,
        extrapaths: List[str] = [],
        innerpath: Optional[str] = None,
        dialect: Optional[Union[Dialect, str]] = None,
        schema: Optional[Union[Schema, str]] = None,
        checklist: Optional[Union[Checklist, str]] = None,
        pipeline: Optional[Union[Pipeline, str]] = None,
        stats: dict = {},
        # Software
        basepath: Optional[str] = None,
        onerror: Optional[IOnerror] = None,
        trusted: Optional[bool] = None,
        detector: Optional[Detector] = None,
        package: Optional[Package] = None,
        control: Optional[Control] = None,
    ):

        # Store state
        self.name = name
        self.type = type
        self.title = title
        self.description = description
        self.homepage = homepage
        self.profiles = profiles.copy()
        self.licenses = licenses.copy()
        self.sources = sources.copy()
        self.path = path
        self.data = data
        self.scheme = scheme
        self.format = format
        self.hashing = hashing
        self.encoding = encoding
        self.mediatype = mediatype
        self.compression = compression
        self.extrapaths = extrapaths.copy()
        self.innerpath = innerpath
        self.stats = stats.copy()
        self.package = package

        # Store dereferenced state
        self.__dialect = dialect
        self.__control = control
        self.__schema = schema
        self.__checklist = checklist
        self.__pipeline = pipeline

        # Store inherited state
        self.__basepath = basepath
        self.__onerror = onerror
        self.__trusted = trusted
        self.__detector = detector

        # Store internal state
        self.__loader: Optional[Loader] = None
        self.__parser: Optional[Parser] = None
        self.__buffer: Optional[IBuffer] = None
        self.__sample: Optional[ISample] = None
        self.__labels: Optional[ILabels] = None
        self.__fragment: Optional[IFragment] = None
        self.__header: Optional[Header] = None
        self.__lookup: Optional[Lookup] = None
        self.__row_stream: Optional[IRowStream] = None

        # Handled by the create hook
        assert source is None

    @classmethod
    def __create__(cls, source: Optional[Any] = None, **options):
        if source is not None:

            # Path
            if isinstance(source, Path):
                source = str(source)

            # Mapping
            elif isinstance(source, Mapping):
                source = {key: value for key, value in source.items()}

            # Descriptor
            if helpers.is_descriptor_source(source):
                return Resource.from_descriptor(source, **options)

            # Path/data
            options["path" if isinstance(source, str) else "data"] = source
            return Resource(**options)

    # TODO: maybe it's possible to do type narrowing here?
    def __enter__(self):
        if self.closed:
            self.open()
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    # TODO: iter cell stream to be PETL-compatible?
    def __iter__(self):
        with helpers.ensure_open(self):
            # TODO: rebase on Inferred/OpenResource?
            # (here and in other places like this)
            assert self.__row_stream
            yield from self.__row_stream

    # State

    name: Optional[str]
    """
    Resource name according to the specs.
    It should be a slugified name of the resource.
    """

    type: Optional[str]
    """
    Type of the data e.g. "table"
    """

    title: Optional[str]
    """
    Resource title according to the specs
    It should a human-oriented title of the resource.
    """

    description: Optional[str]
    """
    Resource description according to the specs
    It should a human-oriented description of the resource.
    """

    homepage: Optional[str]
    """
    A URL for the home on the web that is related to this package.
    For example, github repository or ckan dataset address.
    """

    profiles: List[str]
    """
    Strings identifying the profile of this descriptor.
    For example, `tabular-data-resource`.
    """

    licenses: List[dict]
    """
    The license(s) under which the resource is provided.
    If omitted it's considered the same as the package's licenses.
    """

    sources: List[dict]
    """
    The raw sources for this data resource.
    It MUST be an array of Source objects.
    Each Source object MUST have a title and
    MAY have path and/or email properties.
    """

    path: Optional[str]
    """
    Path to data source
    """

    data: Optional[Any]
    """
    Inline data source
    """

    scheme: Optional[str]
    """
    Scheme for loading the file (file, http, ...).
    If not set, it'll be inferred from `source`.
    """

    format: Optional[str]
    """
    File source's format (csv, xls, ...).
    If not set, it'll be inferred from `source`.
    """

    hashing: Optional[str]
    """
    An algorithm to hash data.
    It defaults to 'md5'.
    """

    encoding: Optional[str]
    """
    Source encoding.
    If not set, it'll be inferred from `source`.
    """

    mediatype: Optional[str]
    """
    Mediatype/mimetype of the resource e.g. “text/csv”,
    or “application/vnd.ms-excel”.  Mediatypes are maintained by the
    Internet Assigned Numbers Authority (IANA) in a media type registry.
    """

    compression: Optional[str]
    """
    Source file compression (zip, ...).
    If not set, it'll be inferred from `source`.
    """

    extrapaths: List[str]
    """
    List of paths to concatenate to the main path.
    It's used for multipart resources.
    """

    innerpath: Optional[str]
    """
    Path within the compressed file.
    It defaults to the first file in the archive (if the source is an archive).
    """

    stats: dict
    """
    Stats dictionary.
    A dict with the following possible properties: hash, bytes, fields, rows.
    """

    package: Optional[Package]
    """
    Parental to this resource package.
    For more information, please check the Package documentation.
    """

    # Props

    @property
    def dialect(self) -> Dialect:
        """
        File Dialect object.
        For more information, please check the Dialect documentation.
        """
        if self.__dialect is None:
            raise FrictionlessException("dialect is not set or inferred")
        if isinstance(self.__dialect, str):
            path = os.path.join(self.basepath, self.__dialect)
            self.__dialect = Dialect.from_descriptor(path)
        return self.__dialect

    @dialect.setter
    def dialect(self, value: Union[Dialect, str]):
        self.__dialect = value

    @property
    def has_dialect(self) -> bool:
        return self.__dialect is not None

    @property
    def schema(self) -> Schema:
        """
        Table Schema object.
        For more information, please check the Schema documentation.
        """
        if self.__schema is None:
            raise FrictionlessException("schema is not set or inferred")
        if isinstance(self.__schema, str):
            path = os.path.join(self.basepath, self.__schema)
            self.__schema = Schema.from_descriptor(path)
        return self.__schema

    @schema.setter
    def schema(self, value: Optional[Union[Schema, str]]):
        self.__schema = value

    @property
    def has_schema(self) -> bool:
        return self.__schema is not None

    @property
    def checklist(self) -> Optional[Checklist]:
        """
        Checklist object.
        For more information, please check the Checklist documentation.
        """
        if isinstance(self.__checklist, str):
            path = os.path.join(self.basepath, self.__checklist)
            self.__checklist = Checklist.from_descriptor(path)
        return self.__checklist

    @checklist.setter
    def checklist(self, value: Optional[Union[Checklist, str]]):
        self.__checklist = value

    @property
    def pipeline(self) -> Optional[Pipeline]:
        """
        Pipeline object.
        For more information, please check the Pipeline documentation.
        """
        if isinstance(self.__pipeline, str):
            path = os.path.join(self.basepath, self.__pipeline)
            self.__pipeline = Pipeline.from_descriptor(path)
        return self.__pipeline

    @pipeline.setter
    def pipeline(self, value: Optional[Union[Pipeline, str]]):
        self.__pipeline = value

    @property
    def basepath(self) -> str:
        """
        A basepath of the resource
        The fullpath of the resource is joined `basepath` and /path`
        """
        if self.__basepath is not None:
            return self.__basepath
        elif self.package:
            return self.package.basepath
        return settings.DEFAULT_BASEPATH

    @basepath.setter
    def basepath(self, value: str):
        self.__basepath = value

    @property
    def onerror(self) -> IOnerror:
        """
        Behaviour if there is an error.
        It defaults to 'ignore'. The default mode will ignore all errors
        on resource level and they should be handled by the user
        being available in Header and Row objects.
        """
        if self.__onerror is not None:
            return self.__onerror  # type: ignore
        elif self.package:
            return self.package.onerror
        return settings.DEFAULT_ONERROR

    @onerror.setter
    def onerror(self, value: IOnerror):
        self.__onerror = value

    @property
    def trusted(self) -> bool:
        """
        Don't raise an exception on unsafe paths.
        A path provided as a part of the descriptor considered unsafe
        if there are path traversing or the path is absolute.
        A path provided as `source` or `path` is alway trusted.
        """
        if self.__trusted is not None:
            return self.__trusted
        elif self.package:
            return self.package.trusted
        return settings.DEFAULT_TRUSTED

    @trusted.setter
    def trusted(self, value: bool):
        self.__trusted = value

    @property
    def detector(self) -> Detector:
        """
        Resource detector.
        For more information, please check the Detector documentation.
        """
        if self.__detector is not None:
            return self.__detector
        elif self.package:
            return self.package.detector
        self.__detector = Detector()
        return self.__detector

    @detector.setter
    def detector(self, value: Detector):
        self.__detector = value

    @property
    def normpath(self) -> str:
        """Normalized path of the resource or raise if not set"""
        if self.path is None:
            raise FrictionlessException("path is not set")
        return helpers.normalize_path(self.basepath, self.path)

    @property
    def normpaths(self) -> List[str]:
        """Normalized paths of the resource or raise if not set"""
        if self.path is None:
            raise FrictionlessException("path is not set")
        normpaths = []
        for path in [self.path] + self.extrapaths:
            normpaths.append(helpers.normalize_path(self.basepath, path))
        return normpaths

    @property
    def normdata(self) -> Any:
        """Normalized data or raise if not set"""
        if self.data is None:
            raise FrictionlessException("data is not set")
        return self.data

    # TODO: add asteriks for user/pass in url
    @property
    def place(self) -> str:
        """Stringified resource location"""
        if self.data:
            return "<memory>"
        elif self.extrapaths:
            return f"{self.path} (multipart)"
        elif self.innerpath:
            return f"{self.path} -> {self.innerpath}"
        elif self.path:
            return self.path
        return ""

    @property
    def memory(self) -> bool:
        """Whether resource is not path based"""
        return self.data is not None

    @property
    def remote(self) -> bool:
        """Whether resource is remote"""
        return helpers.is_remote_path(self.basepath or self.path)

    @property
    def multipart(self) -> bool:
        """Whether resource is multipart"""
        return not self.memory and bool(self.extrapaths)

    @property
    def tabular(self) -> bool:
        """Whether resource is tabular"""
        return self.type == "table"

    @property
    def buffer(self) -> IBuffer:
        """File's bytes used as a sample

        These buffer bytes are used to infer characteristics of the
        source file (e.g. encoding, ...).
        """
        if self.__buffer is None:
            raise FrictionlessException("resource is not open or non binary")
        return self.__buffer

    @property
    def sample(self) -> ISample:
        """Table's lists used as sample.

        These sample rows are used to infer characteristics of the
        source file (e.g. schema, ...).

        Returns:
            list[]?: table sample
        """
        if self.__sample is None:
            raise FrictionlessException("resource is not open or non tabular")
        return self.__sample

    @property
    def labels(self) -> ILabels:
        """
        Returns:
            str[]?: table labels
        """
        if self.__labels is None:
            raise FrictionlessException("resource is not open or non tabular")
        return self.__labels

    @property
    def fragment(self) -> IFragment:
        """Table's lists used as fragment.

        These fragment rows are used internally to infer characteristics of the
        source file (e.g. schema, ...).

        Returns:
            list[]?: table fragment
        """
        if self.__fragment is None:
            raise FrictionlessException("resource is not open or non tabular")
        return self.__fragment

    @property
    def header(self) -> Header:
        """
        Returns:
            str[]?: table header
        """
        if self.__header is None:
            raise FrictionlessException("resource is not open or non tabular")
        return self.__header

    @property
    def lookup(self) -> Lookup:
        """
        Returns:
            str[]?: table lookup
        """
        if self.__lookup is None:
            raise FrictionlessException("resource is not open or non tabular")
        return self.__lookup

    @property
    def byte_stream(self) -> IByteStream:
        """Byte stream in form of a generator

        Yields:
            gen<bytes>?: byte stream
        """
        if self.closed:
            raise FrictionlessException("resource is not open or non binary")
        if not self.__loader:
            self.__loader = system.create_loader(self)
            self.__loader.open()
        return self.__loader.byte_stream

    @property
    def text_stream(self) -> ITextStream:
        """Text stream in form of a generator

        Yields:
            gen<str[]>?: text stream
        """
        if self.closed:
            raise FrictionlessException("resource is not open or non textual")
        if not self.__loader:
            self.__loader = system.create_loader(self)
            self.__loader.open()
        return self.__loader.text_stream

    @property
    def cell_stream(self) -> ICellStream:
        """Cell stream in form of a generator

        Yields:
            gen<any[][]>?: cell stream
        """
        if self.__parser is None:
            raise FrictionlessException("resource is not open or non tabular")
        return self.__parser.cell_stream

    @property
    def row_stream(self) -> IRowStream:
        """Row stream in form of a generator of Row objects

        Yields:
            gen<Row[]>?: row stream
        """
        if self.__row_stream is None:
            raise FrictionlessException("resource is not open or non tabular")
        return self.__row_stream

    # Infer

    def infer(self, *, sample: bool = True, stats: bool = False) -> None:
        """Infer metadata

        Parameters:
            sample? (bool): open file and infer from a sample (default: True)
            stats? (bool): stream file completely and infer stats
        """
        if sample is False:
            self.__prepare_file()
            return
        if not self.closed:
            note = "Resource.infer canot be used on a open resource"
            raise FrictionlessException(errors.ResourceError(note=note))
        with self:
            if not stats:
                # TODO: rework in v6
                self.stats = {}
                self.metadata_assigned.remove("stats")
                return
            stream = self.__row_stream or self.byte_stream
            helpers.pass_through(stream)

    # Open/Close

    def open(self, *, as_file: bool = False):
        """Open the resource as "io.open" does"""

        # Prepare
        self.close()
        self.__prepare_file()

        # Open
        try:

            # Table
            if self.type == "table" and not as_file:
                self.__prepare_parser()
                self.__prepare_buffer()
                self.__prepare_sample()
                self.__prepare_dialect()
                self.__prepare_labels()
                self.__prepare_fragment()
                self.__prepare_schema()
                self.__prepare_header()
                self.__prepare_lookup()
                self.__prepare_row_stream()
                return self

            # File
            else:
                self.__prepare_loader()
                self.__prepare_buffer()
                return self

        # Error
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        """Close the resource as "filelike.close" does"""
        if self.__parser:
            self.__parser.close()
            self.__parser = None
        if self.__loader:
            self.__loader.close()
            self.__loader = None

    @property
    def closed(self) -> bool:
        """Whether the table is closed

        Returns:
            bool: if closed
        """
        return self.__parser is None and self.__loader is None

    def __prepare_file(self):

        # Detect
        self.detector.detect_resource(self)
        system.detect_resource(self)
        if self.__dialect is None:
            self.__dialect = Dialect()
            if self.__control:
                self.__dialect.set_control(self.__control)

        # Validate
        self.metadata_assigned.add("dialect")
        if not self.metadata_valid:
            raise FrictionlessException(self.metadata_errors[0])

    def __prepare_loader(self):

        # Create/open
        self.__loader = system.create_loader(self)
        self.__loader.open()

    def __prepare_buffer(self):

        # From parser
        if self.__parser and self.__parser.requires_loader:
            self.__buffer = self.__parser.loader.buffer

        # From loader
        elif self.__loader:
            self.__buffer = self.__loader.buffer

    def __prepare_parser(self):

        # Create/open
        self.__parser = system.create_parser(self)
        self.__parser.open()

    def __prepare_sample(self):

        # From parser
        if self.__parser:
            self.__sample = self.__parser.sample

    def __prepare_dialect(self):

        # Detect
        self.__dialect = self.detector.detect_dialect(
            self.sample,
            dialect=self.dialect if self.has_dialect else None,
        )

        # Validate
        self.metadata_assigned.add("dialect")
        if not self.dialect.metadata_valid:
            raise FrictionlessException(self.dialect.metadata_errors[0])

    def __prepare_labels(self):

        # From sample
        self.__labels = self.dialect.read_labels(self.sample)

    def __prepare_fragment(self):

        # From sample
        self.__fragment = self.dialect.read_fragment(self.sample)

    def __prepare_schema(self):

        # Detect
        self.__schema = self.detector.detect_schema(
            self.fragment,
            labels=self.labels,
            schema=self.schema if self.has_schema else None,
            field_candidates=system.create_field_candidates(),
        )

        # Validate
        self.metadata_assigned.add("schema")
        if not self.schema.metadata_valid:
            raise FrictionlessException(self.schema.metadata_errors[0])

    def __prepare_header(self):

        # Create header
        self.__header = Header(
            self.__labels,
            fields=self.schema.fields,
            row_numbers=self.dialect.header_rows,
            ignore_case=not self.dialect.header_case,
        )

        # Handle errors
        if not self.header.valid:
            error = self.header.errors[0]
            if self.onerror == "warn":
                warnings.warn(error.message, UserWarning)
            elif self.onerror == "raise":
                raise FrictionlessException(error)

    def __prepare_lookup(self):
        self.__lookup = Lookup()
        for fk in self.schema.foreign_keys:

            # Prepare source
            source_name = fk["reference"]["resource"]
            source_key = tuple(fk["reference"]["fields"])
            if source_name != "" and not self.package:
                continue
            if source_name:
                if not self.package:
                    note = 'package is required for FK: "{fk}"'
                    raise FrictionlessException(errors.ResourceError(note=note))
                if not self.package.has_resource(source_name):
                    note = f'failed to handle a foreign key for resource "{self.name}" as resource "{source_name}" does not exist'
                    raise FrictionlessException(errors.ResourceError(note=note))
                source_res = self.package.get_resource(source_name)
            else:
                source_res = self.to_copy()
            if source_res.has_schema:
                source_res.schema.foreign_keys = []

            # Prepare lookup
            self.__lookup.setdefault(source_name, {})
            if source_key in self.__lookup[source_name]:
                continue
            self.__lookup[source_name][source_key] = set()
            if not source_res:
                continue
            with source_res:
                for row in source_res.row_stream:  # type: ignore
                    cells = tuple(row.get(field_name) for field_name in source_key)
                    if set(cells) == {None}:
                        continue
                    self.__lookup[source_name][source_key].add(cells)

    def __prepare_row_stream(self):

        # TODO: we need to rework this field_info / row code
        # During row streaming we crate a field info structure
        # This structure is optimized and detached version of schema.fields
        # We create all data structures in-advance to share them between rows

        # Create field info
        field_number = 0
        field_info = {"names": [], "objects": [], "mapping": {}}
        for field in self.schema.fields:
            field_number += 1
            field_info["names"].append(field.name)
            field_info["objects"].append(field.to_copy())
            field_info["mapping"][field.name] = (
                field,
                field_number,
                field.create_cell_reader(),
                field.create_cell_writer(),
            )

        # Create state
        memory_unique = {}
        memory_primary = {}
        foreign_groups = []
        is_integrity = bool(self.schema.primary_key)
        for field in self.schema.fields:
            if field.constraints.get("unique"):
                memory_unique[field.name] = {}
                is_integrity = True
        if self.__lookup:
            for fk in self.schema.foreign_keys:
                group = {}
                group["sourceName"] = fk["reference"]["resource"]
                group["sourceKey"] = tuple(fk["reference"]["fields"])
                group["targetKey"] = tuple(fk["fields"])
                foreign_groups.append(group)
                is_integrity = True

        # Create content stream
        enumerated_content_stream = self.dialect.read_enumerated_content_stream(
            self.cell_stream
        )

        # Create row stream
        def row_stream():
            row_count = 0
            for row_number, cells in enumerated_content_stream:
                row_count += 1

                # Create row
                row = Row(
                    cells,
                    field_info=field_info,
                    row_number=row_number,
                )

                # Unique Error
                if is_integrity and memory_unique:
                    for field_name in memory_unique.keys():
                        cell = row[field_name]
                        if cell is not None:
                            match = memory_unique[field_name].get(cell)
                            memory_unique[field_name][cell] = row.row_number
                            if match:
                                func = errors.UniqueError.from_row
                                note = "the same as in the row at position %s" % match
                                error = func(row, note=note, field_name=field_name)
                                row.errors.append(error)

                # Primary Key Error
                if is_integrity and self.schema.primary_key:
                    cells = tuple(row[name] for name in self.schema.primary_key)
                    if set(cells) == {None}:
                        note = 'cells composing the primary keys are all "None"'
                        error = errors.PrimaryKeyError.from_row(row, note=note)
                        row.errors.append(error)
                    else:
                        match = memory_primary.get(cells)
                        memory_primary[cells] = row.row_number
                        if match:
                            if match:
                                note = "the same as in the row at position %s" % match
                                error = errors.PrimaryKeyError.from_row(row, note=note)
                                row.errors.append(error)

                # Foreign Key Error
                if is_integrity and foreign_groups:
                    for group in foreign_groups:
                        group_lookup = self.lookup.get(group["sourceName"])
                        if group_lookup:
                            cells = tuple(row[name] for name in group["targetKey"])
                            if set(cells) == {None}:
                                continue
                            match = cells in group_lookup.get(group["sourceKey"], set())
                            if not match:
                                note = (
                                    'for "%s": values "%s" not found in the lookup table "%s" as "%s"'
                                    % (
                                        ", ".join(group["targetKey"]),
                                        ", ".join(str(d) for d in cells),
                                        group["sourceName"],
                                        ", ".join(group["sourceKey"]),
                                    )
                                )
                                error = errors.ForeignKeyError.from_row(row, note=note)
                                row.errors.append(error)

                # Handle errors
                if self.onerror != "ignore":
                    if not row.valid:
                        error = row.errors[0]
                        if self.onerror == "raise":
                            raise FrictionlessException(error)
                        warnings.warn(error.message, UserWarning)

                # Yield row
                yield row

            # Update stats
            self.stats["fields"] = len(self.schema.fields)
            self.stats["rows"] = row_count

        # Crreate row stream
        self.__row_stream = row_stream()

    # Read

    def read_bytes(self, *, size: Optional[int] = None) -> bytes:
        """Read bytes into memory

        Returns:
            any[][]: resource bytes
        """
        if self.memory:
            return b""
        with helpers.ensure_open(self):
            return self.byte_stream.read1(size)  # type: ignore

    def read_text(self, *, size: Optional[int] = None) -> str:
        """Read text into memory

        Returns:
            str: resource text
        """
        if self.memory:
            return ""
        with helpers.ensure_open(self):
            return self.text_stream.read(size)  # type: ignore

    def read_data(self, *, size: Optional[int] = None) -> Any:
        """Read data into memory

        Returns:
            any: resource data
        """
        if self.data:
            return self.data
        with helpers.ensure_open(self):
            text = self.read_text(size=size)
            data = json.loads(text)
            return data

    def read_cells(self, *, size: Optional[int] = None) -> List[List[Any]]:
        """Read lists into memory

        Returns:
            any[][]: table lists
        """
        with helpers.ensure_open(self):
            result = []
            for cells in self.cell_stream:
                result.append(cells)
                if size and len(result) >= size:
                    break
            return result

    def read_rows(self, *, size=None) -> List[Row]:
        """Read rows into memory

        Returns:
            Row[]: table rows
        """
        with helpers.ensure_open(self):
            rows = []
            for row in self.row_stream:
                rows.append(row)
                if size and len(rows) >= size:
                    break
            return rows

    # Write

    def write(self, target: Any = None, **options) -> Resource:
        """Write this resource to the target resource

        Parameters:
            target (any|Resource): target or target resource instance
            **options (dict): Resource constructor options
        """
        native = isinstance(target, Resource)
        target = target if native else Resource(target, **options)
        target.infer(sample=False)
        parser = system.create_parser(target)
        parser.write_row_stream(self)
        return target

    # Convert

    # TODO: review
    def to_copy(self, **options):
        """Create a copy from the resource

        Returns
            Resource: resource copy
        """
        return super().to_copy(
            data=self.data,
            basepath=self.basepath,
            onerror=self.onerror,
            trusted=self.trusted,
            detector=self.detector,
            package=self.package,
            # TODO: rework with dialect rework
            control=self.__control,
            **options,
        )

    def to_view(self, type="look", **options):
        """Create a view from the resource

        See PETL's docs for more information:
        https://petl.readthedocs.io/en/stable/util.html#visualising-tables

        Parameters:
            type (look|lookall|see|display|displayall): view's type
            **options (dict): options to be passed to PETL

        Returns
            str: resource's view
        """
        assert type in ["look", "lookall", "see", "display", "displayall"]
        view = str(getattr(self.to_petl(normalize=True), type)(**options))
        return view

    def to_snap(self, *, json=False):
        """Create a snapshot from the resource

        Parameters:
            json (bool): make data types compatible with JSON format

        Returns
            list: resource's data
        """
        snap = []
        with helpers.ensure_open(self):
            snap.append(self.header.to_list())
            for row in self.row_stream:
                snap.append(row.to_list(json=json))
        return snap

    def to_inline(self, *, dialect=None):
        """Helper to export resource as an inline data"""
        target = self.write(Resource(format="inline", dialect=dialect))
        return target.data

    def to_pandas(self, *, dialect=None):
        """Helper to export resource as an Pandas dataframe"""
        target = self.write(Resource(format="pandas", dialect=dialect))
        return target.data

    @staticmethod
    def from_petl(view, **options):
        """Create a resource from PETL view"""
        return Resource(data=view, **options)

    def to_petl(self, normalize=False):
        """Export resource as a PETL table"""
        resource = self.to_copy()

        # Define view
        class ResourceView(petl.Table):
            def __iter__(self):
                with resource:
                    if normalize:
                        yield resource.schema.field_names
                        yield from (row.to_list() for row in resource.row_stream)
                        return
                    if not resource.header.missing:
                        yield resource.header.labels
                    yield from (row.cells for row in resource.row_stream)

        return ResourceView()

    # Metadata

    metadata_type = "resource"
    metadata_Error = errors.ResourceError
    metadata_Types = dict(
        dialect=Dialect,
        schema=Schema,
        checklist=Checklist,
        pipeline=Pipeline,
    )
    metadata_profile = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "pattern": settings.NAME_PATTERN},
            "type": {"type": "string", "pattern": settings.TYPE_PATTERN},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "homepage": {"type": "string"},
            "profiles": {"type": "array"},
            "licenses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "path": {"type": "string"},
                        "title": {"type": "string"},
                    },
                },
            },
            "sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "path": {"type": "string"},
                        "email": {"type": "string"},
                    },
                },
            },
            "path": {"type": "string"},
            "data": {"type": ["object", "array"]},
            "scheme": {"type": "string"},
            "format": {"type": "string"},
            "hashing": {"type": "string"},
            "encoding": {"type": "string"},
            "mediatype": {"type": "string"},
            "compression": {"type": "string"},
            "extrapaths": {"type": "array"},
            "innerpath": {"type": "string"},
            "dialect": {"type": ["object", "string"]},
            "schema": {"type": ["object", "string"]},
            "checklist": {"type": ["object", "string"]},
            "pipeline": {"type": ["object", "string"]},
            "stats": {"type": "object"},
        },
    }

    @classmethod
    def metadata_import(cls, descriptor: IDescriptorSource, **options):
        options.setdefault("trusted", False)
        if isinstance(descriptor, str):
            options.setdefault("basepath", helpers.parse_basepath(descriptor))
        descriptor = super().metadata_normalize(descriptor)

        # Url (v0)
        url = descriptor.pop("url", None)
        if url is not None:
            descriptor.setdefault("path", url)

        # Path (v1)
        path = descriptor.get("path")
        if path and isinstance(path, list):
            descriptor["path"] = path[0]
            descriptor["extrapaths"] = path[1:]

        # Profile (v1)
        profile = descriptor.pop("profile", None)
        if profile == "data-resource":
            descriptor["type"] = "file"
        elif profile == "tabular-data-resource":
            descriptor["type"] = "table"
        elif profile:
            descriptor.setdefault("profiles", [])
            descriptor["profiles"].append(profile)

        # Stats (v1)
        for name in ["hash", "bytes"]:
            value = descriptor.pop(name, None)
            if value:
                if name == "hash":
                    hashing, value = helpers.parse_resource_hash(value)
                    if hashing != settings.DEFAULT_HASHING:
                        descriptor["hashing"] = hashing
                descriptor.setdefault("stats", {})
                descriptor["stats"][name] = value

        # Compression (v1.5)
        compression = descriptor.get("compression")
        if compression == "no":
            descriptor.pop("compression")
            note = 'Resource "compression=no" is deprecated in favor not set value'
            note += "(it will be removed in the next major version)"
            warnings.warn(note, UserWarning)

        # Layout (v1.5)
        layout = descriptor.pop("layout", None)
        if layout:
            descriptor.setdefault("dialect", {})
            descriptor["dialect"].update(layout)
            note = 'Resource "layout" is deprecated in favor of "dialect"'
            note += "(it will be removed in the next major version)"
            warnings.warn(note, UserWarning)

        return super().metadata_import(descriptor, **options)

    def metadata_export(self):
        descriptor = super().metadata_export()

        # Data
        data = descriptor.get("data")
        if data is not None and not isinstance(data, (list, dict)):
            descriptor["data"] = []

        # Path (v1)
        if system.standards_version == "v1":
            path = descriptor.get("path")
            extrapaths = descriptor.pop("extrapaths", None)
            if extrapaths:
                descriptor["path"] = []
                if path:
                    descriptor["path"].append(path)
                descriptor["path"].extend(extrapaths)

        # Profile (v1)
        if system.standards_version == "v1":
            type = descriptor.pop("type", None)
            profiles = descriptor.pop("profiles", None)
            if type == "table":
                descriptor["profile"] = "tabular-data-profile"
            elif profiles:
                descriptor["profile"] = profiles[0]

        # Stats (v1)
        if system.standards_version == "v1":
            stats = descriptor.pop("stats", None)
            if stats:
                hash = stats.get("hash")
                bytes = stats.get("bytes")
                if hash is not None:
                    descriptor["hash"] = hash
                if bytes is not None:
                    descriptor["bytes"] = bytes

        return descriptor

    def metadata_validate(self, *, strict=False):
        yield from super().metadata_validate()

        # Required (normal)
        if self.path is None and self.data is None:
            note = 'one of the properties "path" or "data" is required'
            yield errors.ResourceError(note=note)

        # Requried (strict)
        if strict:
            names = ["name", "type", "scheme", "format", "hashing", "encoding"]
            names.append("mediatype")
            if self.tabular:
                names.append("schema")
            for name in names:
                if getattr(self, name, None) is None:
                    note = f'property "{name}" is required in a strict mode'
                    yield errors.ResourceError(note=note)

        # Dialect
        if self.has_dialect:
            yield from self.dialect.metadata_errors

        # Schema
        if self.has_schema:
            yield from self.schema.metadata_errors

        # Checklist
        if self.checklist:
            yield from self.checklist.metadata_errors

        # Pipeline
        if self.pipeline:
            yield from self.pipeline.metadata_errors

        # Contributors/Sources
        for name in ["contributors", "sources"]:
            for item in getattr(self, name, []):
                if item.get("email"):
                    field = fields.StringField(format="email")
                    _, note = field.read_cell(item.get("email"))
                    if note:
                        note = f'property "{name}[].email" is not valid "email"'
                        yield errors.ResourceError(note=note)
        # Custom
        for name in ["missingValues", "fields"]:
            if name in self.custom:
                note = f'"{name}" should be set as "schema.{name}"'
                yield errors.ResourceError(note=note)
