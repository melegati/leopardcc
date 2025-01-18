import csv
from datetime import datetime
from interfaces.TimeSeriesEntry import TimeEntry


def save_time_entries_to_csv(file_path: str, entries: list[TimeEntry]):
    csv_header = list(TimeEntry.__annotations__.keys())

    with open(file_path, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_header)

        writer.writeheader()

        for entry in entries:
            formatted_entry = {
                **entry,
                "timestamp": entry["timestamp"].isoformat() if isinstance(entry["timestamp"], datetime) else entry["timestamp"]
            }
            writer.writerow(formatted_entry)
