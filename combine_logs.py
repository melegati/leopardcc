import os
import argparse
import csv
from collections import defaultdict

def find_csv_file(folder_path):
    """Return the path to the first CSV file in the folder."""
    for item in os.listdir(folder_path):
        if item.endswith('.csv'):
            return os.path.join(folder_path, item)
    return None

def concatenate_csvs(root_dir):
    subdirs = sorted([d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))])
    output_rows = []
    header_written = False
    final_header = []

    # Track run number for each technique
    run_counter = defaultdict(int)

    for subdir in subdirs:
        subdir_path = os.path.join(root_dir, subdir)
        csv_path = find_csv_file(subdir_path)

        if csv_path:
            with open(csv_path, 'r', newline='', encoding='utf-8') as infile:
                run_number = None
                reader = csv.reader(infile)
                header = next(reader)

                # Make sure prompt_strategy column exists
                if 'prompt_strategy' not in header:
                    print(f"Error: 'prompt_strategy' column missing in {csv_path}")
                    continue

                idx_prompt_strategy = header.index('prompt_strategy')
                idx_model = header.index('model')
                idx_project = header.index('project')

                # Set final header only once
                if not header_written:
                    final_header = ['Technique', 'Run'] + header
                    output_rows.append(final_header)
                    header_written = True
                elif header != final_header[2:]:
                    print(f"Warning: Column mismatch in {csv_path}")

                for row in reader:
                    if run_number is None:
                        technique = row[idx_prompt_strategy]
                        model = row[idx_model]
                        project = row[idx_project]
                        key = (technique, model, project)

                        run_counter[key] += 1
                        run_number = run_counter[key]
                    output_rows.append([technique, run_number] + row)
        else:
            print(f"Warning: No CSV file found in {subdir_path}")

    # Write the output CSV
    output_path = os.path.join(root_dir, 'concatenated.csv')
    with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        writer.writerows(output_rows)

    print(f"Concatenated CSV written to: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Concatenate CSVs from subfolders (technique from 'prompt_strategy' column).")
    parser.add_argument("root_folder", type=str, help="Path to the root folder containing subfolders")

    args = parser.parse_args()
    concatenate_csvs(args.root_folder)
