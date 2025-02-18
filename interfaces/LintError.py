from typing import TypedDict


class LintError(TypedDict):
    rule_id: str
    message: str
    file: str
    target_line: int
    erroneous_code: str
    severity: int
