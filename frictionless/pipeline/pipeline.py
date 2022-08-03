from __future__ import annotations
import attrs
import warnings
from typing import Optional, List
from importlib import import_module
from ..exception import FrictionlessException
from ..metadata import Metadata
from .step import Step
from .. import settings
from .. import helpers
from .. import errors


# TODO: raise an exception if we try export a pipeline with function based steps
@attrs.define(kw_only=True)
class Pipeline(Metadata):
    """Pipeline representation"""

    # State

    name: Optional[str] = None
    """NOTE: add docs"""

    title: Optional[str] = None
    """NOTE: add docs"""

    description: Optional[str] = None
    """NOTE: add docs"""

    steps: List[Step] = attrs.field(factory=list)
    """List of transform steps"""

    # Props

    @property
    def step_types(self) -> List[str]:
        return [step.type for step in self.steps]

    # Validate

    def validate(self):
        timer = helpers.Timer()
        errors = self.list_metadata_errors()
        Report = import_module("frictionless").Report
        return Report.from_validation(time=timer.time, errors=errors)

    # Steps

    def add_step(self, step: Step) -> None:
        """Add new step to the schema"""
        self.steps.append(step)

    def has_step(self, type: str) -> bool:
        """Check if a step is present"""
        for step in self.steps:
            if step.type == type:
                return True
        return False

    def get_step(self, type: str) -> Step:
        """Get step by type"""
        for step in self.steps:
            if step.type == type:
                return step
        error = errors.PipelineError(note=f'step "{type}" does not exist')
        raise FrictionlessException(error)

    def set_step(self, step: Step) -> Optional[Step]:
        """Set step by type"""
        if self.has_step(step.type):
            prev_step = self.get_step(step.type)
            index = self.steps.index(prev_step)
            self.steps[index] = step
            return prev_step
        self.add_step(step)

    def remove_step(self, type: str) -> Step:
        """Remove step by type"""
        step = self.get_step(type)
        self.steps.remove(step)
        return step

    def clear_steps(self) -> None:
        """Remove all the steps"""
        self.steps = []

    # Metadata

    metadata_type = "pipeline"
    metadata_Error = errors.PipelineError
    metadata_Types = dict(steps=Step)
    metadata_profile = {
        "type": "object",
        "required": ["steps"],
        "properties": {
            "name": {"type": "string", "pattern": settings.NAME_PATTERN},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "steps": {"type": "array"},
        },
    }

    @classmethod
    def metadata_import(cls, descriptor):
        descriptor = cls.metadata_normalize(descriptor)

        # Tasks (v1.5)
        tasks = descriptor.pop("tasks", [])
        if tasks and isinstance(tasks[0], dict):
            descriptor.setdefault("steps", tasks[0].get("steps"))
            note = 'Pipeline "tasks[].steps" is deprecated in favor of "steps"'
            note += "(it will be removed in the next major version)"
            warnings.warn(note, UserWarning)

        return super().metadata_import(descriptor)

    def metadata_validate(self):
        yield from super().metadata_validate()

        # Steps
        for step in self.steps:
            yield from step.metadata_validate()
