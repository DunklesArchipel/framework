from __future__ import annotations
from importlib import import_module
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional
from ..exception import FrictionlessException
from ..metadata import Metadata
from ..checks import baseline
from .check import Check
from .. import helpers
from .. import errors

if TYPE_CHECKING:
    from ..resource import Resource


# TODO: raise an exception if we try export a checklist with function based checks
@dataclass
class Checklist(Metadata):
    """Checklist representation"""

    # State

    checks: List[Check] = field(default_factory=list)
    """# TODO: add docs"""

    pick_errors: List[str] = field(default_factory=list)
    """# TODO: add docs"""

    skip_errors: List[str] = field(default_factory=list)
    """# TODO: add docs"""

    # Props

    @property
    def check_codes(self) -> List[str]:
        return [check.code for check in self.checks]

    @property
    def scope(self) -> List[str]:
        scope = []
        basics: List[Check] = [baseline()]
        for check in basics + self.checks:
            for Error in check.Errors:
                if self.pick_errors:
                    if Error.code not in self.pick_errors and not set(
                        self.pick_errors
                    ).intersection(Error.tags):
                        continue
                if self.skip_errors:
                    if Error.code in self.skip_errors or set(
                        self.skip_errors
                    ).intersection(Error.tags):
                        continue
                scope.append(Error.code)
        return scope

    # Validate

    def validate(self):
        timer = helpers.Timer()
        errors = self.metadata_errors
        Report = import_module("frictionless").Report
        return Report.from_validation(time=timer.time, errors=errors)

    # Checks

    def add_check(self, check: Check) -> None:
        """Add new check to the schema"""
        self.checks.append(check)

    def has_check(self, code: str) -> bool:
        """Check if a check is present"""
        for check in self.checks:
            if check.code == code:
                return True
        return False

    def get_check(self, code: str) -> Check:
        """Get check by code"""
        for check in self.checks:
            if check.code == code:
                return check
        error = errors.ChecklistError(note=f'check "{code}" does not exist')
        raise FrictionlessException(error)

    def set_check(self, check: Check) -> Optional[Check]:
        """Set check by code"""
        if self.has_check(check.code):
            prev_check = self.get_check(check.code)
            index = self.checks.index(prev_check)
            self.checks[index] = check
            return prev_check
        self.add_check(check)

    def remove_check(self, code: str) -> Check:
        """Remove check by code"""
        check = self.get_check(code)
        self.checks.remove(check)
        return check

    def clear_checks(self) -> None:
        """Remove all the checks"""
        self.checks = []

    # Connect

    def connect(self, resource: Resource) -> List[Check]:
        checks = []
        basics: List[Check] = [baseline()]
        for check in basics + self.checks:
            if check.metadata_valid:
                # TODO: review
                #  check = check.to_copy()
                check.connect(resource)
                checks.append(check)
        return checks

    # Match

    def match(self, error: errors.Error) -> bool:
        if isinstance(error, errors.DataError):
            if error.code not in self.scope:
                return False
        return True

    # Metadata

    metadata_Error = errors.ChecklistError
    metadata_Types = dict(checks=Check)
    metadata_profile = {
        "properties": {
            "checks": {},
            "skipErrors": {},
            "pickErrors": {},
        }
    }

    def metadata_validate(self):
        yield from super().metadata_validate()

        # Checks
        for check in self.checks:
            yield from check.metadata_errors
