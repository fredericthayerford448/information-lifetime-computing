"""User-facing diagnostics (no raw parser exceptions leak to the user)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Union


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    file: str = "<input>"
    line: int = 0
    col: int = 0
    severity: str = "error"

    def format(self) -> str:
        loc = f"{self.file}:{self.line}:{self.col}" if self.line else self.file
        return f"{loc}: {self.severity}[{self.code}]: {self.message}"


class ILCError(Exception):
    """Raised for any user-facing failure; carries one or more Diagnostics."""

    def __init__(self, diagnostics: Union[Diagnostic, Iterable[Diagnostic]]):
        if isinstance(diagnostics, Diagnostic):
            diagnostics = [diagnostics]
        self.diagnostics: List[Diagnostic] = list(diagnostics)
        super().__init__("\n".join(d.format() for d in self.diagnostics))
