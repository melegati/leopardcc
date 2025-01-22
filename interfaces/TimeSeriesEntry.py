from datetime import datetime
from typing import TypedDict


class TimeEntry(TypedDict):
    iteration: int
    timestamp: datetime

    function_file: str
    function_name: str

    old_cc: int
    new_cc: int
    old_prj_avg_cc: float
    new_prj_avg_cc: float
    sent_tokens: int
    received_tokens: int
