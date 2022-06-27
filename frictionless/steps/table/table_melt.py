from typing import Optional, List
from dataclasses import dataclass, field
from ...step import Step
from ...schema import Field


# NOTE:
# We might consider implementing table_preload/cache step
# Some of the following step use **options - we need to review/fix it
# Currently, metadata profiles are not fully finished; will require improvements
# We need to review table_pivot step as it's not fully implemented/tested
# We need to review table_validate step as it's not fully implemented/tested
# We need to review table_write step as it's not fully implemented/tested
# We need to review how we use "target.schema.fields.clear()"


@dataclass
class table_melt(Step):
    """Melt tables"""

    code = "table-melt"

    # Properties

    field_name: str
    """TODO: add docs"""

    variables: Optional[str] = None
    """TODO: add docs"""

    to_field_names: List[str] = field(default_factory=lambda: ["variable", "value"])
    """TODO: add docs"""

    # Transform

    def transform_resource(self, resource):
        table = resource.to_petl()
        field = resource.schema.get_field(self.field_name)
        resource.schema.fields.clear()
        resource.schema.add_field(field)
        for name in self.to_field_names:
            resource.schema.add_field(Field(name=name))
        resource.data = table.melt(  # type: ignore
            key=self.field_name,
            variables=self.variables,
            variablefield=self.to_field_names[0],
            valuefield=self.to_field_names[1],
        )

    # Metadata

    metadata_profile = {  # type: ignore
        "type": "object",
        "required": ["fieldName"],
        "properties": {
            "code": {},
            "fieldName": {"type": "string"},
            "variables": {"type": "array"},
            "toFieldNames": {"type": "array", "minItems": 2, "maxItems": 2},
        },
    }
