# type: ignore
from __future__ import annotations
from ...pipeline import Step
from ...platform import platform
from ...resource import Resource


# NOTE:
# We might consider implementing table_preload/cache step
# Some of the following step use **options - we need to review/fix it
# Currently, metadata profiles are not fully finished; will require improvements
# We need to review table_pivot step as it's not fully implemented/tested
# We need to review table_validate step as it's not fully implemented/tested
# We need to review table_write step as it's not fully implemented/tested
# We need to review how we use "target.schema.fields.clear()"


# TODO: migrate
class table_merge(Step):
    """Merge tables"""

    type = "table-merge"

    def __init__(
        self,
        descriptor=None,
        *,
        resource=None,
        field_names=None,
        ignore_fields=False,
        sort_by_field=False,
    ):
        self.setinitial("resource", resource)
        self.setinitial("fieldNames", field_names)
        self.setinitial("ignoreFields", ignore_fields)
        self.setinitial("sortByField", sort_by_field)
        super().__init__(descriptor)

    # Transform

    def transform_resource(self, resource):
        target = resource
        source = self.get("resource")
        field_names = self.get("fieldNames")
        ignore_fields = self.get("ignoreFields")
        sort_by_field = self.get("sortByField")
        if isinstance(source, str):
            source = target.package.get_resource(source)
        elif isinstance(source, dict):
            source = Resource(source)
        source.infer()  # type: ignore
        view1 = target.to_petl()
        view2 = source.to_petl()  # type: ignore

        # Ignore fields
        if ignore_fields:
            for field in source.schema.fields[len(target.schema.fields) :]:  # type: ignore
                target.schema.add_field(field)
            resource.data = platform.petl.stack(view1, view2)

        # Default
        else:
            for field in source.schema.fields:  # type: ignore
                if field.name not in target.schema.field_names:
                    target.schema.add_field(field)
            if field_names:
                for field in list(target.schema.fields):
                    if field.name not in field_names:
                        target.schema.remove_field(field.name)
            if sort_by_field:
                key = sort_by_field
                resource.data = platform.petl.mergesort(
                    view1, view2, key=key, header=field_names
                )
            else:
                resource.data = platform.petl.cat(view1, view2, header=field_names)

    # Metadata

    metadata_profile_patch = {
        "required": ["resource"],
        "properties": {
            "resource": {},
            "fieldNames": {"type": "array"},
            "ignoreFields": {},
            "sortByField": {},
        },
    }
