import csv
import shutil
import tempfile
from pathlib import Path

EXPECTED_COLUMNS = [
    "iteration",
    "project",
    "prompt_strategy",
    "verification_strategy",
    "model",
    "timestamp",
    "function_file",
    "function_name",
    "old_cc",
    "new_cc",
    "old_prj_avg_cc",
    "new_prj_avg_cc",
    "old_fn_count",
    "new_fn_count",
    "old_avg_nloc",
    "new_avg_nloc",
    "sent_tokens",
    "received_tokens",
    "result",
]

NEW_COLUMN = "reasoning_effort"
INSERT_AFTER = "model"
LOG_FILE_NAME = "log.txt"


def build_output_columns():
    cols = EXPECTED_COLUMNS.copy()
    idx = cols.index(INSERT_AFTER) + 1
    cols.insert(idx, NEW_COLUMN)
    return cols


OUTPUT_COLUMNS = build_output_columns()


def extract_reasoning_effort(log_path: Path) -> str:
    if not log_path.is_file():
        return ""

    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            marker = "Reasoning effort:"
            if marker in line:
                return line.split(marker, 1)[1].strip()

    return ""


def update_csv(csv_path: Path, reasoning_effort: str) -> None:
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError(f"{csv_path}: missing header row")

        input_columns = reader.fieldnames

        if input_columns == OUTPUT_COLUMNS:
            rows = list(reader)
        elif input_columns == EXPECTED_COLUMNS:
            rows = list(reader)
        else:
            raise ValueError(
                f"{csv_path}: unexpected columns.\n"
                f"Found: {input_columns}\n"
                f"Expected: {EXPECTED_COLUMNS} or {OUTPUT_COLUMNS}"
            )

    for row in rows:
        row[NEW_COLUMN] = reasoning_effort

    with tempfile.NamedTemporaryFile(
        "w", newline="", encoding="utf-8", delete=False, dir=csv_path.parent
    ) as tmp:
        tmp_path = Path(tmp.name)
        writer = csv.DictWriter(tmp, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    shutil.move(str(tmp_path), str(csv_path))


def find_single_file(subfolder: Path, pattern: str) -> Path | None:
    matches = sorted(p for p in subfolder.glob(pattern) if p.is_file())

    if not matches:
        return None

    if len(matches) > 1:
        raise ValueError(f"{subfolder}: multiple files found for {pattern}: {[p.name for p in matches]}")

    return matches[0]


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Update CSV files in immediate subfolders using reasoning effort from each subfolder's log.txt."
    )
    parser.add_argument(
        "folder",
        help="Parent folder containing subfolders with CSV files and log.txt files",
    )
    args = parser.parse_args()

    root = Path(args.folder).expanduser().resolve()

    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    for subfolder in sorted(p for p in root.iterdir() if p.is_dir()):
        csv_file = find_single_file(subfolder, "*.csv")

        if csv_file is None:
            print(f"Skipping {subfolder}: no CSV file found")
            continue

        log_file = subfolder / LOG_FILE_NAME
        reasoning_effort = extract_reasoning_effort(log_file)

        update_csv(csv_file, reasoning_effort)
        print(f"Updated {csv_file} (reasoning_effort={reasoning_effort!r})")


if __name__ == "__main__":
    main()