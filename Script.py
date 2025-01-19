from datetime import datetime, timezone
from OpenAIWrapper import OpenAIWrapper
from projects.Expressjs import Expressjs
from projects.D3Shape import D3Shape
from prompt_strategies.ChoiEtAl import ChoiEtAl as ChoiEtAlPrompt
from verification_strategies.ChoiEtAl import ChoiEtAl as ChoiEtAlVerification
from util.Logger import get_logger, add_log_file_handler
from util.CSVWriter import save_time_entries_to_csv
from LizardHelper import compute_cyclomatic_complexity, get_functions_sorted_by_complexity, compute_avg_cc_for_project
from Refactorer import improve_function
from interfaces.Function import Function
from interfaces.NotImprovableException import NotImprovableException
import os
from interfaces.TimeSeriesEntry import TimeEntry


def prepare_log_dir() -> str:
    timestamp = filename = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d-%H-%M-%S")
    log_dir = "logs/" + timestamp
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    return log_dir


def prepare_conversation_wrapper(log_dir: str) -> OpenAIWrapper:
    with open('openai-key.txt', "r", encoding="utf-8") as key_file:
        api_key = key_file.read()
    conversation_log_file_path = log_dir + "/conversation.json"

    model = "gpt-4o-mini"
    max_content_length = -1
    get_logger().info("Creating OpenAIWrapper for model " + model +
                      " with max. content length " + str(max_content_length))

    wrapper = OpenAIWrapper(
        api_key=api_key,
        log_path=conversation_log_file_path,
        model=model,
        max_context_length=max_content_length)

    return wrapper


def main() -> None:
    project = D3Shape()
    prompt_strategy = ChoiEtAlPrompt()
    verification_strategy = ChoiEtAlVerification()

    log_dir = prepare_log_dir()
    add_log_file_handler(log_dir + "/log.txt")

    wrapper = prepare_conversation_wrapper(log_dir)

    complexity_info = compute_cyclomatic_complexity(
        project.path + project.code_dir)
    most_complex = get_functions_sorted_by_complexity(complexity_info)

    improved_functions: list[Function] = list()
    disregarded_functions: list[Function] = list()

    original_avg_project_cc = compute_avg_cc_for_project(
        project.path + project.code_dir)
    time_series: list[TimeEntry] = []
    try:
        for idx, lizard_result in enumerate(most_complex[:20]):
            function = Function(lizard_result, project,
                                wrapper, prompt_strategy)
            try:
                get_logger().info("Refactoring function " + function.lizard_result.long_name +
                                  " from file " + function.lizard_result.filename +
                                  " with CC: " + str(function.lizard_result.cyclomatic_complexity))

                improve_function(function, improved_functions +
                                 disregarded_functions, verification_strategy)

                get_logger().info("Function successfully improved")
                function.apply_changes_to_target()
                improved_functions.append(function)

            except NotImprovableException as e:
                get_logger().info("Function could not be improved, disregarding")
                function.restore_original_code()
                disregarded_functions.append(function)

            finally:
                old_prj_cc = original_avg_project_cc if idx == 0 else time_series[
                    idx-1]['new_prj_avg_cc']
                new_prj_cc = compute_avg_cc_for_project(
                    project.dirty_path + project.code_dir)

                get_logger().info("Old CC of function: " + str(function.old_cc))
                get_logger().info("New CC of function: " + str(function.new_cc))
                get_logger().info("Old CC of project: " + str(old_prj_cc))
                get_logger().info("New CC of project: " + str(new_prj_cc))

                entry: TimeEntry = {
                    'iteration': idx,
                    'timestamp': datetime.now(timezone.utc),
                    'function_file': function.original_path,
                    'function_name': function.lizard_result.long_name,
                    'old_cc': function.old_cc,
                    'new_cc': function.new_cc,
                    'old_prj_avg_cc': old_prj_cc,
                    'new_prj_avg_cc': new_prj_cc
                }
                time_series.append(entry)
                csv_path = log_dir + "/" + project.name + ".csv"
                save_time_entries_to_csv(csv_path, time_series)

    except BaseException as e:
        get_logger().error(e)
        raise e


if __name__ == "__main__":
    main()
