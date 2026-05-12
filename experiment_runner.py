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
COMBINED_PROJECT_VALUES_FILE = "combined_project_values.csv"


class ExperimentError(Exception):
    pass


@dataclass(frozen=True)
class TestDefinition:
    variable: str
    type: str
    test: str
    count_if: Optional[Any] = None
    combine_runs: Optional[str] = None
    alternative: Optional[str] = None


@dataclass(frozen=True)
class ModelDefinition:
    name: str
    reasoning_effort: Optional[str] = None


@dataclass(frozen=True)
class RunCombination:
    project: str
    prompt_strategy: str
    model: str
    reasoning_effort: Optional[str] = None
    run_index: int = 1

    def key(self) -> Tuple[str, str, str, Optional[str], int]:
        return (self.project, self.prompt_strategy, self.model, self.reasoning_effort, self.run_index)


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
    VALID_COMBINE_RUNS = {"average", "standard_deviation", "maximum", "minimum"}

    def __init__(self, settings: Dict[str, Any]) -> None:
        self.settings = settings

    def validate(self) -> Dict[str, Any]:
        prompt_values = self._ensure_string_list("prompt-strategy")
        model_values = self._ensure_model_list("model")
        project_values = self._ensure_string_list("project")
        iterations = self._ensure_positive_int("iterations", default=1)
        script = self._ensure_script_path()
        number_of_runs = self._ensure_positive_int("number_of_runs", default=1)

        if len(prompt_values) > 2:
            raise ExperimentError("'prompt-strategy' must contain one or two values.")
        if len(model_values) > 2:
            raise ExperimentError("'model' must contain one or two values.")

        if len(prompt_values) == 2 and len(model_values) == 2:
            raise ExperimentError(
                "Invalid settings: the experiment may compare prompt strategies or models, but never both at the same time."
            )

        single_option_mode = len(prompt_values) == 1 and len(model_values) == 1
        tests_raw = self.settings.get("tests")

        if single_option_mode:
            if tests_raw:
                raise ExperimentError(
                    "No statistical test will be performed when both 'prompt-strategy' and 'model' contain only one option. Remove 'tests' from the settings."
                )
            tests: List[TestDefinition] = []
        else:
            tests = self._parse_tests(tests_raw, number_of_runs)

        return {
            "prompt-strategy": prompt_values,
            "model": model_values,
            "project": project_values,
            "iterations": iterations,
            "tests": tests,
            "script": script,
            "number_of_runs": number_of_runs,
            "single_option_mode": single_option_mode,
        }

    def _ensure_string_list(self, key: str) -> List[str]:
        value = self.settings.get(key)
        if not isinstance(value, list) or not value:
            raise ExperimentError(f"'{key}' must be a non-empty list.")
        if not all(isinstance(item, str) and item.strip() for item in value):
            raise ExperimentError(f"'{key}' must contain only non-empty strings.")
        return value

    def _ensure_model_list(self, key: str) -> List[ModelDefinition]:
        value = self.settings.get(key)
        if not isinstance(value, list) or not value:
            raise ExperimentError(f"'{key}' must be a non-empty list.")
        parsed: List[ModelDefinition] = []
        for idx, item in enumerate(value, start=1):
            if isinstance(item, str) and item.strip():
                parsed.append(ModelDefinition(name=item.strip(), reasoning_effort=None))
                continue
            if isinstance(item, dict):
                name = item.get("name")
                reasoning_effort = item.get("reasoning_effort", item.get("reasoaning_effort"))
                if not isinstance(name, str) or not name.strip():
                    raise ExperimentError(f"'{key}' item #{idx}: 'name' must be a non-empty string.")
                if reasoning_effort is not None and (not isinstance(reasoning_effort, str) or not reasoning_effort.strip()):
                    raise ExperimentError(f"'{key}' item #{idx}: 'reasoning_effort' must be a non-empty string when provided.")
                parsed.append(ModelDefinition(name=name.strip(), reasoning_effort=reasoning_effort.strip() if isinstance(reasoning_effort, str) else None))
                continue
            raise ExperimentError(f"'{key}' item #{idx} must be either a string or a mapping with 'name' and optional 'reasoning_effort'.")
        return parsed

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

    def _parse_tests(self, raw_tests: Any, number_of_runs: int) -> List[TestDefinition]:
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
            combine_runs = test_def.get("combine_runs")
            alternative = test_def.get("alternative")

            if not isinstance(variable, str) or not variable.strip():
                raise ExperimentError(f"Test #{idx}: 'variable' must be a non-empty string.")
            if test_type not in {"last_iteration", "count", "last_iteration_reduction"}:
                raise ExperimentError(f"Test #{idx}: 'type' must be 'last_iteration', 'count', or 'last_iteration_reduction'.")
            if not isinstance(test_name, str) or not test_name.strip():
                raise ExperimentError(f"Test #{idx}: 'test' must be a non-empty string.")
            if test_type == "count" and "count_if" not in test_def:
                raise ExperimentError(f"Test #{idx}: 'count_if' is required for count tests.")

            if number_of_runs > 1:
                if combine_runs not in self.VALID_COMBINE_RUNS:
                    raise ExperimentError(
                        f"Test #{idx}: 'combine_runs' is required when 'number_of_runs' is greater than one and must be one of average, standard_deviation, maximum, minimum."
                    )
            elif combine_runs is not None and combine_runs not in self.VALID_COMBINE_RUNS:
                raise ExperimentError(
                    f"Test #{idx}: 'combine_runs' must be one of average, standard_deviation, maximum, minimum when provided."
                )

            if test_name == "wilcoxon_signed_rank":
                if alternative is None:
                    alternative = "two-sided"
                if alternative not in {"two-sided", "greater", "less"}:
                    raise ExperimentError(
                        f"Test #{idx}: 'alternative' for wilcoxon_signed_rank must be one of two-sided, greater, less."
                    )
            elif alternative is not None:
                raise ExperimentError(
                    f"Test #{idx}: 'alternative' is only supported for wilcoxon_signed_rank."
                )

            parsed.append(
                TestDefinition(
                    variable=variable,
                    type=test_type,
                    test=test_name,
                    count_if=count_if,
                    combine_runs=combine_runs,
                    alternative=alternative,
                )
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
                model=model.name,
                reasoning_effort=model.reasoning_effort,
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

    def scan(self) -> Dict[Tuple[str, str, str, Optional[str], int], RunRecord]:
        grouped: Dict[Tuple[str, str, str, Optional[str]], List[RunRecord]] = {}
        if not self.log_dir.exists():
            return {}

        for run_dir in sorted(path for path in self.log_dir.iterdir() if path.is_dir()):
            for csv_file in sorted(run_dir.glob("*.csv")):
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
                reasoning_effort = None
                if "reasoning_effort" in frame.columns and not pd.isna(last_row.get("reasoning_effort")):
                    reasoning_effort = str(last_row["reasoning_effort"])
                base_key = (
                    str(last_row["project"]),
                    str(last_row["prompt_strategy"]),
                    str(last_row["model"]),
                    reasoning_effort,
                )
                grouped.setdefault(base_key, []).append(
                    RunRecord(
                        combination=RunCombination(base_key[0], base_key[1], base_key[2], base_key[3], run_index=0),
                        run_dir=run_dir,
                        csv_file=csv_file,
                    )
                )
                break

        indexed: Dict[Tuple[str, str, str, Optional[str], int], RunRecord] = {}
        for base_key, records in grouped.items():
            for idx, record in enumerate(sorted(records, key=lambda item: str(item.run_dir)), start=1):
                combination = RunCombination(base_key[0], base_key[1], base_key[2], base_key[3], run_index=idx)
                indexed[combination.key()] = RunRecord(combination, record.run_dir, record.csv_file)
        return indexed


class RunExecutor:
    def __init__(self, experiment_dir: Path, log_dir: Path, settings: Dict[str, Any]) -> None:
        self.experiment_dir = experiment_dir
        self.log_dir = log_dir
        self.settings = settings

    def execute_missing(
        self,
        combinations: Sequence[RunCombination],
        existing_runs: Dict[Tuple[str, str, str, Optional[str], int], RunRecord],
    ) -> Dict[Tuple[str, str, str, Optional[str], int], RunRecord]:
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
            if combination.reasoning_effort:
                command.append(f"--reasoning-effort={combination.reasoning_effort}")
            result = subprocess.run(command)
            if result.returncode != 0:
                raise ExperimentError(
                    "A run failed for combination "
                    f"project={combination.project}, prompt_strategy={combination.prompt_strategy}, "
                    f"model={combination.model}, run_index={combination.run_index}."
                )

            after = {path.resolve() for path in self.log_dir.iterdir() if path.is_dir()}
            record = self._find_new_record_for_combination(combination, sorted(after - before), completed)
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
        completed: Dict[Tuple[str, str, str, Optional[str], int], RunRecord],
    ) -> Optional[RunRecord]:
        used_dirs = {record.run_dir.resolve() for record in completed.values()}
        matches: List[RunRecord] = []
        for run_dir in candidate_dirs:
            if run_dir.resolve() in used_dirs:
                continue
            for csv_file in sorted(run_dir.glob("*.csv")):
                record = self._record_matches(combination, run_dir, csv_file)
                if record is not None:
                    matches.append(record)
        return matches[0] if len(matches) == 1 else None

    def _record_matches(self, combination: RunCombination, run_dir: Path, csv_file: Path) -> Optional[RunRecord]:
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
        record_reasoning_effort = None
        if "reasoning_effort" in frame.columns and not pd.isna(last_row.get("reasoning_effort")):
            record_reasoning_effort = str(last_row["reasoning_effort"])
        if (
            str(last_row["project"]) == combination.project
            and str(last_row["prompt_strategy"]) == combination.prompt_strategy
            and str(last_row["model"]) == combination.model
            and record_reasoning_effort == combination.reasoning_effort
        ):
            return RunRecord(combination, run_dir, csv_file)
        return None


class StatisticCalculator:
    @staticmethod
    def run_test(
        test_name: str,
        sample_a: Sequence[float],
        sample_b: Sequence[float],
        alternative: str = "two-sided",
    ) -> Tuple[float, float]:
        if len(sample_a) != len(sample_b):
            raise ExperimentError("Paired statistical tests require both samples to have the same size.")
        if len(sample_a) == 0:
            raise ExperimentError("No paired observations were available for the statistical test.")
        if test_name == "wilcoxon_signed_rank":
            stat = stats.wilcoxon(sample_a, sample_b, zero_method="wilcox", alternative=alternative)
            return float(stat.statistic), float(stat.pvalue)
        if test_name == "paired_t_test":
            stat = stats.ttest_rel(sample_a, sample_b, nan_policy="raise")
            return float(stat.statistic), float(stat.pvalue)
        raise ExperimentError(f"Unsupported statistical test: {test_name}")

    @staticmethod
    def effect_size(test_name: str, sample_a: Sequence[float], sample_b: Sequence[float]) -> Tuple[str, float]:
        if len(sample_a) != len(sample_b):
            raise ExperimentError("Effect size calculation requires paired samples of equal size.")
        if len(sample_a) == 0:
            raise ExperimentError("No paired observations were available for the effect size calculation.")
        if test_name == "paired_t_test":
            differences = pd.Series(sample_a, dtype=float) - pd.Series(sample_b, dtype=float)
            std_diff = float(differences.std(ddof=1)) if len(differences) > 1 else 0.0
            return ("cohens_dz", 0.0 if std_diff == 0.0 else float(differences.mean() / std_diff))
        if test_name == "wilcoxon_signed_rank":
            differences = [float(a) - float(b) for a, b in zip(sample_a, sample_b)]
            non_zero = [value for value in differences if value != 0]
            if not non_zero:
                return ("rank_biserial_correlation", 0.0)
            abs_values = [abs(value) for value in non_zero]
            ranks = stats.rankdata(abs_values, method="average")
            positive_rank_sum = sum(rank for rank, value in zip(ranks, non_zero) if value > 0)
            negative_rank_sum = sum(rank for rank, value in zip(ranks, non_zero) if value < 0)
            total_rank_sum = positive_rank_sum + negative_rank_sum
            return (
                "rank_biserial_correlation",
                0.0 if total_rank_sum == 0 else float((positive_rank_sum - negative_rank_sum) / total_rank_sum),
            )
        raise ExperimentError(f"Unsupported test for effect size calculation: {test_name}")

    @staticmethod
    def interpret_effect_size(effect_size_name: str, effect_size_value: float) -> str:
        magnitude = abs(effect_size_value)
        if effect_size_name == "cohens_dz":
            if magnitude < 0.2:
                return "negligible"
            if magnitude < 0.5:
                return "small"
            if magnitude < 0.8:
                return "medium"
            return "large"
        if effect_size_name == "rank_biserial_correlation":
            if magnitude < 0.1:
                return "negligible"
            if magnitude < 0.3:
                return "small"
            if magnitude < 0.5:
                return "medium"
            return "large"
        raise ExperimentError(f"Unsupported effect size interpretation: {effect_size_name}")


class ResultsAnalyzer:
    def __init__(self, settings: Dict[str, Any], run_records: Dict[Tuple[str, str, str, Optional[str], int], RunRecord]) -> None:
        self.settings = settings
        self.run_records = run_records

    def analyze(self) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
        return self._analyze_single_option_mode() if self.settings["single_option_mode"] else self._analyze_comparison_mode()

    def _analyze_comparison_mode(self) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
        comparison_axis = self._detect_comparison_axis()
        comparison_values = self._comparison_values(comparison_axis)
        fixed_axis = "model" if comparison_axis == "prompt-strategy" else "prompt-strategy"
        grouped = self._group_records_by_pairing_unit(comparison_axis)
        runs_rows: List[Dict[str, Any]] = []
        analysis_rows: List[Dict[str, Any]] = []
        combined_project_rows: List[Dict[str, Any]] = []

        for pair_key, option_map in grouped.items():
            if set(option_map.keys()) != set(comparison_values):
                raise ExperimentError(f"Missing comparison options for group {pair_key}.")
            left_records = option_map[comparison_values[0]]
            right_records = option_map[comparison_values[1]]
            for record in left_records + right_records:
                runs_rows.append(self._run_row(record))
            combined_row: Dict[str, Any] = {
                "project": left_records[0].combination.project,
                "comparison_axis": comparison_axis,
                "option_a": comparison_values[0],
                "option_b": comparison_values[1],
                "fixed_value": getattr(left_records[0].combination, self._python_attr(fixed_axis)),
            }
            for test_def in self.settings["tests"]:
                left_value = self._combine_run_metrics(left_records, test_def)
                right_value = self._combine_run_metrics(right_records, test_def)
                analysis_rows.append(
                    {
                        "group": str(pair_key),
                        "comparison_axis": comparison_axis,
                        "option_a": comparison_values[0],
                        "option_b": comparison_values[1],
                        "fixed_value": getattr(left_records[0].combination, self._python_attr(fixed_axis)),
                        "project": left_records[0].combination.project,
                        "variable": test_def.variable,
                        "metric_type": test_def.type,
                        "count_if": test_def.count_if,
                        "combine_runs": test_def.combine_runs or "not_applicable",
                        "test": test_def.test,
                        "value_a": left_value,
                        "value_b": right_value,
                    }
                )
                metric_name = self._combined_metric_column_name(test_def)
                combined_row[f"{comparison_values[0]}__{metric_name}"] = left_value
                combined_row[f"{comparison_values[1]}__{metric_name}"] = right_value
                if test_def.type == "last_iteration_reduction":
                    left_first, left_last = self._combine_first_last_values(left_records, test_def)
                    right_first, right_last = self._combine_first_last_values(right_records, test_def)
                    combined_row[f"{comparison_values[0]}__{test_def.variable}__first_iteration__{test_def.combine_runs or 'not_applicable'}"] = left_first
                    combined_row[f"{comparison_values[0]}__{test_def.variable}__last_iteration__{test_def.combine_runs or 'not_applicable'}"] = left_last
                    combined_row[f"{comparison_values[1]}__{test_def.variable}__first_iteration__{test_def.combine_runs or 'not_applicable'}"] = right_first
                    combined_row[f"{comparison_values[1]}__{test_def.variable}__last_iteration__{test_def.combine_runs or 'not_applicable'}"] = right_last
            combined_project_rows.append(combined_row)

        analysis_frame = pd.DataFrame(analysis_rows)
        if analysis_frame.empty:
            raise ExperimentError("No analysis rows were produced.")

        summary_rows: List[Dict[str, Any]] = []
        for test_def in self.settings["tests"]:
            combine_runs_value = test_def.combine_runs or "not_applicable"
            subset = analysis_frame[
                (analysis_frame["variable"] == test_def.variable)
                & (analysis_frame["metric_type"] == test_def.type)
                & (analysis_frame["test"] == test_def.test)
                & (analysis_frame["combine_runs"] == combine_runs_value)
            ]
            sample_a = subset["value_a"].tolist()
            sample_b = subset["value_b"].tolist()
            statistic, pvalue = StatisticCalculator.run_test(
                test_def.test,
                sample_a,
                sample_b,
                alternative=test_def.alternative or "two-sided",
            )
            effect_size_name, effect_size_value = StatisticCalculator.effect_size(test_def.test, sample_a, sample_b)
            summary_rows.append(
                {
                    "comparison_axis": comparison_axis,
                    "option_a": comparison_values[0],
                    "option_b": comparison_values[1],
                    "variable": test_def.variable,
                    "metric_type": test_def.type,
                    "count_if": test_def.count_if,
                    "combine_runs": combine_runs_value,
                    "test": test_def.test,
                    "alternative": test_def.alternative or "not_applicable",
                    "paired_samples": len(subset),
                    "mean_a": subset["value_a"].mean(),
                    "mean_b": subset["value_b"].mean(),
                    "statistic": statistic,
                    "pvalue": pvalue,
                    "effect_size_name": effect_size_name,
                    "effect_size_value": effect_size_value,
                    "effect_size_interpretation": StatisticCalculator.interpret_effect_size(effect_size_name, effect_size_value),
                    "significant_0_05": bool(pvalue < 0.05),
                }
            )

        runs_frame = pd.DataFrame(runs_rows).drop_duplicates().sort_values(["project", "prompt_strategy", "model", "run_index"])
        summary_frame = pd.DataFrame(summary_rows)
        combined_frame = None
        if self.settings["number_of_runs"] > 1:
            combined_frame = pd.DataFrame(combined_project_rows).sort_values(["project", "fixed_value"])
        return runs_frame, summary_frame, combined_frame

    def _analyze_single_option_mode(self) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
        new_columns = ["new_prj_avg_cc", "new_fn_count", "new_avg_nloc"]
        old_columns = ["old_prj_avg_cc", "old_fn_count", "old_avg_nloc"]
        last_iteration_old_cc_column = "old_cc"
        grouped: Dict[Tuple[str, str, str], List[RunRecord]] = {}
        runs_rows: List[Dict[str, Any]] = []
        summary_rows: List[Dict[str, Any]] = []

        for record in self.run_records.values():
            grouped.setdefault((record.combination.project, record.combination.prompt_strategy, record.combination.model), []).append(record)

        for key, records in sorted(grouped.items()):
            if len(records) != self.settings["number_of_runs"]:
                raise ExperimentError(f"Expected {self.settings['number_of_runs']} runs for {key}, found {len(records)}.")
            new_metric_values: Dict[str, List[float]] = {column: [] for column in new_columns}
            old_metric_values: Dict[str, List[float]] = {column: [] for column in old_columns}
            last_iteration_old_cc_values: List[float] = []
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
                    if pd.isna(first_row[column]):
                        raise ExperimentError(f"First iteration value for '{column}' is missing.")
                    old_metric_values[column].append(float(first_row[column]))
                for column in new_columns:
                    if column not in frame.columns:
                        raise ExperimentError(f"Column '{column}' was not found in one of the result CSV files.")
                    if pd.isna(last_row[column]):
                        raise ExperimentError(f"Last iteration value for '{column}' is missing.")
                    new_metric_values[column].append(float(last_row[column]))
                if last_iteration_old_cc_column not in frame.columns:
                    raise ExperimentError(f"Column '{last_iteration_old_cc_column}' was not found in one of the result CSV files.")
                if pd.isna(last_row[last_iteration_old_cc_column]):
                    raise ExperimentError(f"Last iteration value for '{last_iteration_old_cc_column}' is missing.")
                last_iteration_old_cc_values.append(float(last_row[last_iteration_old_cc_column]))

            reduction_prj_avg_cc = [self._percentage_change(o, n, "reduction") for o, n in zip(old_metric_values["old_prj_avg_cc"], new_metric_values["new_prj_avg_cc"])]
            increase_fn_count = [self._percentage_change(o, n, "increase") for o, n in zip(old_metric_values["old_fn_count"], new_metric_values["new_fn_count"])]
            reduction_avg_nloc = [self._percentage_change(o, n, "reduction") for o, n in zip(old_metric_values["old_avg_nloc"], new_metric_values["new_avg_nloc"])]

            summary_rows.append(
                {
                    "project": key[0],
                    "prompt_strategy": key[1],
                    "model": key[2],
                    "number_of_runs": self.settings["number_of_runs"],
                    "avg_old_cc_last_iteration": sum(last_iteration_old_cc_values) / len(last_iteration_old_cc_values),
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

        runs_frame = pd.DataFrame(runs_rows).drop_duplicates().sort_values(["project", "prompt_strategy", "model", "run_index"])
        summary_frame = pd.DataFrame(summary_rows)
        return runs_frame, summary_frame, None

    def _group_records_by_pairing_unit(self, comparison_axis: str) -> Dict[Tuple[str, str], Dict[str, List[RunRecord]]]:
        groups: Dict[Tuple[str, str], Dict[str, List[RunRecord]]] = {}
        for record in self.run_records.values():
            if comparison_axis == "prompt-strategy":
                pair_key = (record.combination.project, self._comparison_label_from_record(record.combination, "model"))
                option_value = record.combination.prompt_strategy
            else:
                pair_key = (record.combination.project, record.combination.prompt_strategy)
                option_value = self._comparison_label_from_record(record.combination, "model")
            groups.setdefault(pair_key, {}).setdefault(option_value, []).append(record)
        for pair_key, option_map in groups.items():
            for option_value, records in option_map.items():
                option_map[option_value] = sorted(records, key=lambda item: item.combination.run_index)
        return groups

    def _combine_first_last_values(self, records: Sequence[RunRecord], test_def: TestDefinition) -> Tuple[float, float]:
        first_column = self._old_column_name(test_def.variable)
        first_values: List[float] = []
        last_values: List[float] = []
        for record in records:
            frame = pd.read_csv(record.csv_file)
            if first_column not in frame.columns:
                raise ExperimentError(f"Column '{first_column}' was not found in one of the result CSV files.")
            if test_def.variable not in frame.columns:
                raise ExperimentError(f"Column '{test_def.variable}' was not found in one of the result CSV files.")
            if "iteration" not in frame.columns:
                raise ExperimentError("Column 'iteration' is required in result CSV files.")
            ordered = frame.sort_values("iteration")
            first_value = ordered.iloc[0][first_column]
            last_value = ordered.iloc[-1][test_def.variable]
            if pd.isna(first_value):
                raise ExperimentError(f"First iteration value for '{first_column}' is missing.")
            if pd.isna(last_value):
                raise ExperimentError(f"Last iteration value for '{test_def.variable}' is missing.")
            first_values.append(float(first_value))
            last_values.append(float(last_value))
        return self._combine_numeric_values(first_values, test_def.combine_runs), self._combine_numeric_values(last_values, test_def.combine_runs)

    @staticmethod
    def _old_column_name(variable_name: str) -> str:
        if variable_name.startswith("new_"):
            return "old_" + variable_name[4:]
        raise ExperimentError(
            f"Cannot infer the corresponding old-variable name for '{variable_name}'. Expected a variable starting with 'new_'."
        )

    def _combined_metric_column_name(self, test_def: TestDefinition) -> str:
        parts = [test_def.variable, test_def.type]
        if test_def.type == "count" and test_def.count_if is not None:
            parts.append(f"count_if_{test_def.count_if}")
        if test_def.combine_runs:
            parts.append(test_def.combine_runs)
        return "__".join(str(part).replace(" ", "_") for part in parts)

    def _combine_run_metrics(self, records: Sequence[RunRecord], test_def: TestDefinition) -> float:
        if len(records) != self.settings["number_of_runs"]:
            raise ExperimentError(f"Expected {self.settings['number_of_runs']} runs but found {len(records)} for comparison aggregation.")
        per_run_values = [self._extract_metric(pd.read_csv(record.csv_file), test_def) for record in records]
        return self._combine_numeric_values(per_run_values, test_def.combine_runs)

    def _combine_numeric_values(self, values: Sequence[float], combine_runs: Optional[str]) -> float:
        if len(values) == 1:
            return float(values[0])
        if combine_runs == "average":
            return float(pd.Series(values, dtype=float).mean())
        if combine_runs == "standard_deviation":
            return float(pd.Series(values, dtype=float).std(ddof=1)) if len(values) > 1 else 0.0
        if combine_runs == "maximum":
            return float(max(values))
        if combine_runs == "minimum":
            return float(min(values))
        raise ExperimentError("A valid 'combine_runs' value is required when combining multiple runs.")

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
        if test_def.type == "last_iteration_reduction":
            first_value = ordered.iloc[0][test_def.variable]
            last_value = ordered.iloc[-1][test_def.variable]
            if pd.isna(first_value):
                raise ExperimentError(f"First iteration value for '{test_def.variable}' is missing.")
            if pd.isna(last_value):
                raise ExperimentError(f"Last iteration value for '{test_def.variable}' is missing.")
            return self._percentage_change(float(first_value), float(last_value), "reduction")
        if test_def.type == "count":
            return float((ordered[test_def.variable] == test_def.count_if).sum())
        raise ExperimentError(f"Unsupported metric type: {test_def.type}")

    @staticmethod
    def _percentage_change(old_value: float, new_value: float, mode: str) -> float:
        if old_value == 0:
            raise ExperimentError("Cannot compute percentage change when the original value is zero.")
        if mode == "reduction":
            return ((old_value - new_value) / old_value) * 100.0
        if mode == "increase":
            return ((new_value - old_value) / old_value) * 100.0
        raise ExperimentError(f"Unsupported percentage change mode: {mode}")

    def _comparison_values(self, comparison_axis: str) -> List[str]:
        if comparison_axis == "model":
            return [self._model_label(model) for model in self.settings["model"]]
        return list(self.settings[comparison_axis])

    @staticmethod
    def _model_label(model: ModelDefinition) -> str:
        return f"{model.name} [reasoning_effort={model.reasoning_effort}]" if model.reasoning_effort else model.name

    def _comparison_label_from_record(self, combination: RunCombination, axis: str) -> str:
        if axis == "model":
            return self._model_label(ModelDefinition(combination.model, combination.reasoning_effort))
        return getattr(combination, self._python_attr(axis))

    def _detect_comparison_axis(self) -> str:
        return "prompt-strategy" if len(self.settings["prompt-strategy"]) == 2 else "model"

    def _run_row(self, record: RunRecord) -> Dict[str, Any]:
        return {
            "project": record.combination.project,
            "prompt_strategy": record.combination.prompt_strategy,
            "model": record.combination.model,
            "reasoning_effort": record.combination.reasoning_effort,
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
        combinations = CombinationPlanner(settings).build()
        existing_runs = ExistingRunScanner(self.log_dir).scan()
        completed_runs = RunExecutor(self.experiment_dir, self.log_dir, settings).execute_missing(combinations, existing_runs)
        missing = [combo for combo in combinations if combo.key() not in completed_runs]
        if missing:
            raise ExperimentError(f"Some combinations were not completed: {missing}")
        runs_frame, summary_frame, combined_frame = ResultsAnalyzer(settings, completed_runs).analyze()
        runs_frame.to_csv(self.experiment_dir / RUNS_SUMMARY_FILE, index=False)
        summary_frame.to_csv(self.experiment_dir / RESULTS_SUMMARY_FILE, index=False)
        if combined_frame is not None:
            combined_frame.to_csv(self.experiment_dir / COMBINED_PROJECT_VALUES_FILE, index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run and analyze an experiment defined by experiment.yml in the given folder.")
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
