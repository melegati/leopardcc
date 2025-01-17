from typing import TypedDict


class TestError(TypedDict):
    expectation: str
    message_stack: str
    test_file: str
    target_line: int | None
