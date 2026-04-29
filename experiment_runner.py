import argparse
import itertools
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
import yaml

try:
    from scipy import stats
except ImportError as exc:  # pragma: no cover
    raise SystemExit("scipy is required to run this script.") from exc


SETTINGS_FILE = "experiment.yml"
RESULTS_SUMMARY_FILE = "analysis_summary.csv"
RUNS_SUMMARY_FILE = "completed_runs.csv"
SINGLE_MODE_SUMMARY_FILE = "analysis_summary.csv"


class ExperimentError(Exception):
    pass


@dataclass(frozen=True)
class TestDefinition:
    variable: str
    type: str
    test: str
    count_if: Optional[Any] = None


@dataclass(frozen=True)
class RunCombination:
    project: str
    prompt_strategy: str
    model: str
    run_index: int = 1

    def key(self) -> Tuple[str, str, str, int]:
        return (self.project, self.prompt_strategy, self.model, self.run_index)


@dataclass
class RunRecord:
    combination: RunCombination
    run_dir: Path
    csv_file: Path


class SettingsLoader:
    def __init__(self, experiment_dir: Path) -> None:
        self.experiment_dir = experiment_dir
        self.settings_path = experiment_dir / SETTINGS_FILE

    def load(self) -> Dict[str, Any]:
        if not self.settings_path.exists():
            raise ExperimentError(
                f"Missing settings file: {self.settings_path}. Aborting experiment."
            )

        with self.settings_path.open("r", encoding="utf-8") as handle:
            settings = yaml.safe_load(handle) or {}

        if not isinstance(settings, dict):
            raise ExperimentError("The settings file must contain a YAML mapping at the top level.")

        return settings


class SettingsValidator:
    def __init__(self, settings: Dict[str, Any]) -> None:
        self.settings = settings

    def validate(self) -> Dict[str, Any]:
        prompt_values = self._ensure_string_list("prompt-strategy")
        model_values = self._ensure_string_list("model")
        project_values = self._ensure_string_list("project")
        iterations = self._ensure_positive_int("iterations", default=1)
        script = self._ensure_script_path()
        number_of_runs = self._ensure_positive_int("number_of_runs", default=1)

        if len(prompt_values) > 2:
            raise ExperimentError("'prompt-strategy' must contain one or two values.")
        if len(model_values) > 2:
            raise ExperimentError("'model' must contain one or two values.")

        compare_prompt = len(prompt_values) == 2
        compare_model = len(model_values) == 2
        single_option_mode = len(prompt_values) == 1 and len(model_values) == 1

        if compare_prompt and compare_model:
            raise ExperimentError(
                "Invalid settings: the experiment may compare prompt strategies or models, but never both at the same time."
            )

        tests_raw = self.settings.get("tests")

        if single_option_mode:
            if tests_raw:
                raise ExperimentError(
                    "No statistical test will be performed when both 'prompt-strategy' and 'model' contain only one option. Remove 'tests' from the settings."
                )
            return {
                "prompt-strategy": prompt_values,
                "model": model_values,
                "project": project_values,
                "iterations": iterations,
                "tests": [],
                "script": script,
                "number_of_runs": number_of_runs,
                "single_option_mode": True,
            }

        tests = self._parse_tests(tests_raw)
        return {
            "prompt-strategy": prompt_values,
            "model": model_values,
            "project": project_values,
            "iterations": iterations,
            "tests": tests,
            "script": script,
            "number_of_runs": 1,
            "single_option_mode": False,
        }

    def _ensure_string_list(self, key: str) -> List[str]:
        value = self.settings.get(key)
        if not isinstance(value, list) or not value:
            raise ExperimentError(f"'{key}' must be a non-empty list.")
        if not all(isinstance(item, str) and item.strip() for item in value):
            raise ExperimentError(f"'{key}' must contain only non-empty strings.")
        return value

    def _ensure_positive_int(self, key: str, default: int) -> int:
        value = self.settings.get(key, default)
        if not isinstance(value, int) or value <= 0:
            raise ExperimentError(f"'{key}' must be a positive integer.")
        return value

    def _ensure_script_path(self) -> str:
        value = self.settings.get("script", "Script.py")
        if not isinstance(value, str) or not value.strip():
            raise ExperimentError("'script' must be a non-empty string when provided.")
        return value

    def _parse_tests(self, raw_tests: Any) -> List[TestDefinition]:
        if not isinstance(raw_tests, list) or not raw_tests:
            raise ExperimentError("'tests' must be a non-empty list when a comparison will be performed.")

        parsed: List[TestDefinition] = []
        for idx, test_def in enumerate(raw_tests, start=1):
            if not isinstance(test_def, dict):
                raise ExperimentError(f"Test #{idx} must be a mapping.")

            variable = test_def.get("variable")
            test_type = test_def.get("type")
            test_name = test_def.get("test")
            count_if = test_def.get("count_if")

            if not isinstance(variable, str) or not variable.strip():
                raise ExperimentError(f"Test #{idx}: 'variable' must be a non-empty string.")
            if test_type not in {"last_iteration", "count"}:
                raise ExperimentError(f"Test #{idx}: 'type' must be 'last_iteration' or 'count'.")
            if not isinstance(test_name, str) or not test_name.strip():
                raise ExperimentError(f"Test #{idx}: 'test' must be a non-empty string.")
            if test_type == "count" and "count_if" not in test_def:
                raise ExperimentError(f"Test #{idx}: 'count_if' is required for count tests.")

            parsed.append(
                TestDefinition(variable=variable, type=test_type, test=test_name, count_if=count_if)
            )
        return parsed


class CombinationPlanner:
    def __init__(self, settings: Dict[str, Any]) -> None:
        self.settings = settings

    def build(self) -> List[RunCombination]:
        runs = range(1, self.settings["number_of_runs"] + 1)
        return [
            RunCombination(
                project=project,
                prompt_strategy=prompt_strategy,
                model=model,
                run_index=run_index,
            )
            for prompt_strategy, model, project, run_index in itertools.product(
                self.settings["prompt-strategy"],
                self.settings["model"],
                self.settings["project"],
                runs,
            )
        ]


class ExistingRunScanner:
    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir

    def scan(self) -> Dict[Tuple[str, str, str, int], RunRecord]:
        grouped: Dict[Tuple[str, str, str], List[RunRecord]] = {}
        if not self.log_dir.exists():
            return {}

        for run_dir in sorted([path for path in self.log_dir.iterdir() if path.is_dir()]):
            csv_files = sorted(run_dir.glob("*.csv"))
            if not csv_files:
                continue

            for csv_file in csv_files:
                try:
                    frame = pd.read_csv(csv_file)
                except Exception:
                    continue
                if frame.empty:
                    continue
                required = {"project", "prompt_strategy", "model", "iteration"}
                if not required.issubset(frame.columns):
                    continue
                last_row = frame.sort_values("iteration").iloc[-1]
                base_key = (
                    str(last_row["project"]),
                    str(last_row["prompt_strategy"]),
                    str(last_row["model"]),
                )
                grouped.setdefault(base_key, []).append(
                    RunRecord(
                        combination=RunCombination(
                            project=base_key[0],
                            prompt_strategy=base_key[1],
                            model=base_key[2],
                            run_index=0,
                        ),
                        run_dir=run_dir,
                        csv_file=csv_file,
                    )
                )
                break

        indexed: Dict[Tuple[str, str, str, int], RunRecord] = {}
        for base_key, records in grouped.items():
            for idx, record in enumerate(sorted(records, key=lambda item: str(item.run_dir)), start=1):
                combination = RunCombination(
                    project=base_key[0],
                    prompt_strategy=base_key[1],
                    model=base_key[2],
                    run_index=idx,
                )
                indexed[combination.key()] = RunRecord(
                    combination=combination,
                    run_dir=record.run_dir,
                    csv_file=record.csv_file,
                )
        return indexed


class RunExecutor:
    def __init__(self, experiment_dir: Path, log_dir: Path, settings: Dict[str, Any]) -> None:
        self.experiment_dir = experiment_dir
        self.log_dir = log_dir
        self.settings = settings

    def execute_missing(
        self,
        combinations: Sequence[RunCombination],
        existing_runs: Dict[Tuple[str, str, str, int], RunRecord],
    ) -> Dict[Tuple[str, str, str, int], RunRecord]:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        completed = dict(existing_runs)

        for combination in combinations:
            if combination.key() in completed:
                continue

            before = {path.resolve() for path in self.log_dir.iterdir() if path.is_dir()}
            command = [
                sys.executable,
                self.settings["script"],
                f"--project={combination.project}",
                f"--prompt-strategy={combination.prompt_strategy}",
                f"--model={combination.model}",
                f"--base-log-dir={self.log_dir}",
                f"--iterations={self.settings['iterations']}",
            ]

            result = subprocess.run(command)
            if result.returncode != 0:
                raise ExperimentError(
                    "A run failed for combination "
                    f"project={combination.project}, "
                    f"prompt_strategy={combination.prompt_strategy}, "
                    f"model={combination.model}, run_index={combination.run_index}."
                )

            after = {path.resolve() for path in self.log_dir.iterdir() if path.is_dir()}
            new_dirs = sorted(after - before)
            record = self._find_new_record_for_combination(combination, new_dirs, completed)
            if record is None:
                raise ExperimentError(
                    "The run completed but its CSV results could not be uniquely assigned for combination "
                    f"project={combination.project}, prompt_strategy={combination.prompt_strategy}, "
                    f"model={combination.model}, run_index={combination.run_index}."
                )
            completed[combination.key()] = record

        return completed

    def _find_new_record_for_combination(
        self,
        combination: RunCombination,
        candidate_dirs: Iterable[Path],
        completed: Dict[Tuple[str, str, str, int], RunRecord],
    ) -> Optional[RunRecord]:
        used_dirs = {record.run_dir.resolve() for record in completed.values()}
        matches: List[RunRecord] = []
        for run_dir in candidate_dirs:
            if run_dir.resolve() in used_dirs:
                continue
            csv_files = sorted(run_dir.glob("*.csv"))
            for csv_file in csv_files:
                record = self._record_matches(combination, run_dir, csv_file)
                if record is not None:
                    matches.append(record)
        if len(matches) == 1:
            return matches[0]
        return None

    def _record_matches(
        self, combination: RunCombination, run_dir: Path, csv_file: Path
    ) -> Optional[RunRecord]:
        try:
            frame = pd.read_csv(csv_file)
        except Exception:
            return None
        if frame.empty:
            return None
        required = {"project", "prompt_strategy", "model", "iteration"}
        if not required.issubset(frame.columns):
            return None
        last_row = frame.sort_values("iteration").iloc[-1]
        if (
            str(last_row["project"]) == combination.project
            and str(last_row["prompt_strategy"]) == combination.prompt_strategy
            and str(last_row["model"]) == combination.model
        ):
            return RunRecord(combination=combination, run_dir=run_dir, csv_file=csv_file)
        return None


class StatisticCalculator:
    @staticmethod
    def run_test(test_name: str, sample_a: Sequence[float], sample_b: Sequence[float]) -> Tuple[float, float]:
        if len(sample_a) != len(sample_b):
            raise ExperimentError("Paired statistical tests require both samples to have the same size.")
        if len(sample_a) == 0:
            raise ExperimentError("No paired observations were available for the statistical test.")

        if test_name == "wilcoxon_signed_rank":
            stat = stats.wilcoxon(sample_a, sample_b, zero_method="wilcox", alternative="two-sided")
            return float(stat.statistic), float(stat.pvalue)
        if test_name == "paired_t_test":
            stat = stats.ttest_rel(sample_a, sample_b, nan_policy="raise")
            return float(stat.statistic), float(stat.pvalue)

        raise ExperimentError(f"Unsupported statistical test: {test_name}")


class ResultsAnalyzer:
    def __init__(self, settings: Dict[str, Any], run_records: Dict[Tuple[str, str, str, int], RunRecord]) -> None:
        self.settings = settings
        self.run_records = run_records

    def analyze(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        if self.settings["single_option_mode"]:
            return self._analyze_single_option_mode()
        return self._analyze_comparison_mode()

    def _analyze_comparison_mode(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        comparison_axis = self._detect_comparison_axis()
        comparison_values = self.settings[comparison_axis]
        fixed_axis = "model" if comparison_axis == "prompt-strategy" else "prompt-strategy"

        runs_rows = []
        analysis_rows = []

        grouped = self._group_records_by_pairing_unit(comparison_axis)
        for pair_key, compared_records in grouped.items():
            if len(compared_records) != 2:
                raise ExperimentError(
                    f"Expected exactly 2 runs for paired comparison in group {pair_key}, found {len(compared_records)}."
                )

            ordered_records = sorted(
                compared_records,
                key=lambda record: comparison_values.index(
                    getattr(record.combination, self._python_attr(comparison_axis))
                ),
            )

            for record in ordered_records:
                runs_rows.append(self._run_row(record))

            frames = [pd.read_csv(record.csv_file) for record in ordered_records]
            for test_def in self.settings["tests"]:
                left_value = self._extract_metric(frames[0], test_def)
                right_value = self._extract_metric(frames[1], test_def)
                analysis_rows.append(
                    {
                        "group": str(pair_key),
                        "comparison_axis": comparison_axis,
                        "option_a": self._comparison_value(ordered_records[0], comparison_axis),
                        "option_b": self._comparison_value(ordered_records[1], comparison_axis),
                        "fixed_value": getattr(
                            ordered_records[0].combination, self._python_attr(fixed_axis)
                        ),
                        "project": ordered_records[0].combination.project,
                        "variable": test_def.variable,
                        "metric_type": test_def.type,
                        "test": test_def.test,
                        "value_a": left_value,
                        "value_b": right_value,
                    }
                )

        analysis_frame = pd.DataFrame(analysis_rows)
        if analysis_frame.empty:
            raise ExperimentError("No analysis rows were produced.")

        summary_rows = []
        for test_def in self.settings["tests"]:
            subset = analysis_frame[
                (analysis_frame["variable"] == test_def.variable)
                & (analysis_frame["metric_type"] == test_def.type)
                & (analysis_frame["test"] == test_def.test)
            ]
            statistic, pvalue = StatisticCalculator.run_test(
                test_def.test,
                subset["value_a"].tolist(),
                subset["value_b"].tolist(),
            )
            summary_rows.append(
                {
                    "comparison_axis": comparison_axis,
                    "option_a": comparison_values[0],
                    "option_b": comparison_values[1],
                    "variable": test_def.variable,
                    "metric_type": test_def.type,
                    "count_if": test_def.count_if,
                    "test": test_def.test,
                    "paired_samples": len(subset),
                    "mean_a": subset["value_a"].mean(),
                    "mean_b": subset["value_b"].mean(),
                    "statistic": statistic,
                    "pvalue": pvalue,
                    "significant_0_05": bool(pvalue < 0.05),
                }
            )

        runs_frame = pd.DataFrame(runs_rows).drop_duplicates().sort_values(
            ["project", "prompt_strategy", "model", "run_index"]
        )
        summary_frame = pd.DataFrame(summary_rows)
        return runs_frame, summary_frame

    def _analyze_single_option_mode(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        new_columns = ["new_prj_avg_cc", "new_fn_count", "new_avg_nloc"]
        old_columns = ["old_prj_avg_cc", "old_fn_count", "old_avg_nloc"]
        runs_rows = []
        summary_rows = []
        grouped: Dict[Tuple[str, str, str], List[RunRecord]] = {}

        for record in self.run_records.values():
            grouped.setdefault(
                (record.combination.project, record.combination.prompt_strategy, record.combination.model),
                [],
            ).append(record)

        for key, records in sorted(grouped.items()):
            if len(records) != self.settings["number_of_runs"]:
                raise ExperimentError(
                    f"Expected {self.settings['number_of_runs']} runs for {key}, found {len(records)}."
                )

            new_metric_values: Dict[str, List[float]] = {column: [] for column in new_columns}
            old_metric_values: Dict[str, List[float]] = {column: [] for column in old_columns}
            for record in sorted(records, key=lambda item: item.combination.run_index):
                runs_rows.append(self._run_row(record))
                frame = pd.read_csv(record.csv_file)
                if "iteration" not in frame.columns:
                    raise ExperimentError("Column 'iteration' is required in result CSV files.")
                ordered = frame.sort_values("iteration")
                first_row = ordered.iloc[0]
                last_row = ordered.iloc[-1]

                for column in old_columns:
                    if column not in frame.columns:
                        raise ExperimentError(f"Column '{column}' was not found in one of the result CSV files.")
                    value = first_row[column]
                    if pd.isna(value):
                        raise ExperimentError(f"First iteration value for '{column}' is missing.")
                    old_metric_values[column].append(float(value))

                for column in new_columns:
                    if column not in frame.columns:
                        raise ExperimentError(f"Column '{column}' was not found in one of the result CSV files.")
                    value = last_row[column]
                    if pd.isna(value):
                        raise ExperimentError(f"Last iteration value for '{column}' is missing.")
                    new_metric_values[column].append(float(value))

            reduction_prj_avg_cc = [
                self._percentage_change(old_value, new_value, mode="reduction")
                for old_value, new_value in zip(old_metric_values["old_prj_avg_cc"], new_metric_values["new_prj_avg_cc"])
            ]
            increase_fn_count = [
                self._percentage_change(old_value, new_value, mode="increase")
                for old_value, new_value in zip(old_metric_values["old_fn_count"], new_metric_values["new_fn_count"])
            ]
            reduction_avg_nloc = [
                self._percentage_change(old_value, new_value, mode="reduction")
                for old_value, new_value in zip(old_metric_values["old_avg_nloc"], new_metric_values["new_avg_nloc"])
            ]

            summary_rows.append(
                {
                    "project": key[0],
                    "prompt_strategy": key[1],
                    "model": key[2],
                    "number_of_runs": self.settings["number_of_runs"],
                    "avg_old_prj_avg_cc": sum(old_metric_values["old_prj_avg_cc"]) / len(old_metric_values["old_prj_avg_cc"]),
                    "avg_new_prj_avg_cc": sum(new_metric_values["new_prj_avg_cc"]) / len(new_metric_values["new_prj_avg_cc"]),
                    "stddev_new_prj_avg_cc": pd.Series(new_metric_values["new_prj_avg_cc"]).std(ddof=1) if len(new_metric_values["new_prj_avg_cc"]) > 1 else 0.0,
                    "avg_reduction_pct_prj_avg_cc": sum(reduction_prj_avg_cc) / len(reduction_prj_avg_cc),
                    "stddev_reduction_pct_prj_avg_cc": pd.Series(reduction_prj_avg_cc).std(ddof=1) if len(reduction_prj_avg_cc) > 1 else 0.0,
                    "avg_old_fn_count": sum(old_metric_values["old_fn_count"]) / len(old_metric_values["old_fn_count"]),
                    "avg_new_fn_count": sum(new_metric_values["new_fn_count"]) / len(new_metric_values["new_fn_count"]),
                    "stddev_new_fn_count": pd.Series(new_metric_values["new_fn_count"]).std(ddof=1) if len(new_metric_values["new_fn_count"]) > 1 else 0.0,
                    "avg_increase_pct_fn_count": sum(increase_fn_count) / len(increase_fn_count),
                    "stddev_increase_pct_fn_count": pd.Series(increase_fn_count).std(ddof=1) if len(increase_fn_count) > 1 else 0.0,
                    "avg_old_avg_nloc": sum(old_metric_values["old_avg_nloc"]) / len(old_metric_values["old_avg_nloc"]),
                    "avg_new_avg_nloc": sum(new_metric_values["new_avg_nloc"]) / len(new_metric_values["new_avg_nloc"]),
                    "stddev_new_avg_nloc": pd.Series(new_metric_values["new_avg_nloc"]).std(ddof=1) if len(new_metric_values["new_avg_nloc"]) > 1 else 0.0,
                    "avg_reduction_pct_avg_nloc": sum(reduction_avg_nloc) / len(reduction_avg_nloc),
                    "stddev_reduction_pct_avg_nloc": pd.Series(reduction_avg_nloc).std(ddof=1) if len(reduction_avg_nloc) > 1 else 0.0,
                }
            )

        runs_frame = pd.DataFrame(runs_rows).drop_duplicates().sort_values(
            ["project", "prompt_strategy", "model", "run_index"]
        )
        summary_frame = pd.DataFrame(summary_rows)
        return runs_frame, summary_frame

    def _group_records_by_pairing_unit(
        self, comparison_axis: str
    ) -> Dict[Tuple[str, str], List[RunRecord]]:
        groups: Dict[Tuple[str, str], List[RunRecord]] = {}
        for record in self.run_records.values():
            if comparison_axis == "prompt-strategy":
                key = (record.combination.project, record.combination.model)
            else:
                key = (record.combination.project, record.combination.prompt_strategy)
            groups.setdefault(key, []).append(record)
        return groups

    def _extract_metric(self, frame: pd.DataFrame, test_def: TestDefinition) -> float:
        if test_def.variable not in frame.columns:
            raise ExperimentError(f"Column '{test_def.variable}' was not found in one of the result CSV files.")
        if "iteration" not in frame.columns:
            raise ExperimentError("Column 'iteration' is required in result CSV files.")

        ordered = frame.sort_values("iteration")
        if test_def.type == "last_iteration":
            value = ordered.iloc[-1][test_def.variable]
            if pd.isna(value):
                raise ExperimentError(f"Last iteration value for '{test_def.variable}' is missing.")
            return float(value)

        if test_def.type == "count":
            count = (ordered[test_def.variable] == test_def.count_if).sum()
            return float(count)

        raise ExperimentError(f"Unsupported metric type: {test_def.type}")

    def _detect_comparison_axis(self) -> str:
        return "prompt-strategy" if len(self.settings["prompt-strategy"]) == 2 else "model"

    def _comparison_value(self, record: RunRecord, comparison_axis: str) -> str:
        return getattr(record.combination, self._python_attr(comparison_axis))

    @staticmethod
    def _percentage_change(old_value: float, new_value: float, mode: str) -> float:
        if old_value == 0:
            raise ExperimentError("Cannot compute percentage change when the original value is zero.")
        if mode == "reduction":
            return ((old_value - new_value) / old_value) * 100.0
        if mode == "increase":
            return ((new_value - old_value) / old_value) * 100.0
        raise ExperimentError(f"Unsupported percentage change mode: {mode}")

    def _run_row(self, record: RunRecord) -> Dict[str, Any]:
        return {
            "project": record.combination.project,
            "prompt_strategy": record.combination.prompt_strategy,
            "model": record.combination.model,
            "run_index": record.combination.run_index,
            "run_dir": str(record.run_dir),
            "csv_file": str(record.csv_file),
        }

    @staticmethod
    def _python_attr(name: str) -> str:
        return name.replace("-", "_")


class ExperimentRunner:
    def __init__(self, experiment_dir: Path) -> None:
        self.experiment_dir = experiment_dir.resolve()
        self.log_dir = self.experiment_dir / "logs"

    def run(self) -> None:
        settings = SettingsValidator(SettingsLoader(self.experiment_dir).load()).validate()
        planner = CombinationPlanner(settings)
        combinations = planner.build()

        scanner = ExistingRunScanner(self.log_dir)
        existing_runs = scanner.scan()

        executor = RunExecutor(self.experiment_dir, self.log_dir, settings)
        completed_runs = executor.execute_missing(combinations, existing_runs)

        missing = [combo for combo in combinations if combo.key() not in completed_runs]
        if missing:
            raise ExperimentError(f"Some combinations were not completed: {missing}")

        runs_frame, summary_frame = ResultsAnalyzer(settings, completed_runs).analyze()
        runs_frame.to_csv(self.experiment_dir / RUNS_SUMMARY_FILE, index=False)
        output_name = SINGLE_MODE_SUMMARY_FILE if settings["single_option_mode"] else RESULTS_SUMMARY_FILE
        summary_frame.to_csv(self.experiment_dir / output_name, index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run and analyze an experiment defined by experiment.yml in the given folder."
    )
    parser.add_argument("experiment_folder", help="Folder containing experiment.yml")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        ExperimentRunner(Path(args.experiment_folder)).run()
    except ExperimentError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"ERROR: Required file was not found: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
