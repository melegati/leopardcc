from datetime import datetime, timezone
from llm_wrappers.OpenAIWrapper import OpenAIWrapper
from projects.Expressjs import Expressjs
from projects.D3Shape import D3Shape
from projects.Underscore import Underscore
from prompt_strategies.ChoiEtAl import ChoiEtAl as ChoiEtAlPrompt
from verification_strategies.ChoiEtAl import ChoiEtAl as ChoiEtAlVerification
from util.Logger import get_logger, add_log_file_handler
from util.CSVWriter import save_time_entries_to_csv
from helpers.LizardHelper import compute_cyclomatic_complexity, get_functions_sorted_by_complexity, compute_avg_cc_for_project
from Refactorer import improve_function
from interfaces.Function import Function
from interfaces.NotImprovableException import NotImprovableException
from interfaces.LlmWrapperInterface import LLMWrapperInterface
import os
from interfaces.TimeSeriesEntry import TimeEntry
from git import Repo


def prepare_log_dir(project_name: str) -> str:
    timestamp = filename = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d-%H-%M-%S")
    log_dir = "logs/" + timestamp + "-" + project_name
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    return log_dir


def prepare_conversation_wrapper(log_path: str) -> LLMWrapperInterface:
    with open('openai-key.txt', "r", encoding="utf-8") as key_file:
        api_key = key_file.read()

    model = "gpt-4o-mini"
    get_logger().info("Creating OpenAIWrapper for model " + model)

    llm_wrapper = OpenAIWrapper(
        api_key=api_key,
        log_path=log_path,
        model=model)

    return llm_wrapper


def save_git_diff_patch(repo: Repo, function: Function, log_dir: str, idx: int):
    diff = repo.git.diff(function.target_path)

    patch_dir = log_dir + '/patches'
    if not os.path.exists(patch_dir):
        os.makedirs(patch_dir)

    patch_file_path = patch_dir + '/' + str(idx) + '-' + function.lizard_result.name + '.diff'
    with open(patch_file_path, "w", encoding="utf-8") as patch_file:
        patch_file.write(diff)
    
    repo.git.add(function.target_path)
    commit_message = 'apply patch for refactoring iteration ' + str(idx) + ' for fn ' +  function.lizard_result.name
    repo.index.commit(commit_message, skip_hooks=True)


def main() -> None:
    project = Expressjs()
    prompt_strategy = ChoiEtAlPrompt()
    verification_strategy = ChoiEtAlVerification()

    log_dir = prepare_log_dir(project.name)
    add_log_file_handler(log_dir + "/log.txt")

    complexity_info = compute_cyclomatic_complexity(
        project.path + project.code_dir)
    most_complex = get_functions_sorted_by_complexity(complexity_info)

    improved_functions: list[Function] = list()
    disregarded_functions: list[Function] = list()

    repo = Repo(project.target_path)

    original_avg_project_cc = compute_avg_cc_for_project(
        project.path + project.code_dir)
    time_series: list[TimeEntry] = []
    
    consecutive_exception_count = 0
    for idx, lizard_result in enumerate(most_complex[:20]):
        try:
            get_logger().info("Refactoring function #" + str(idx) + ": " + lizard_result.long_name +
                                " from file " + lizard_result.filename +
                                " with CC: " + str(lizard_result.cyclomatic_complexity))

            llm_wrapper_logpath = log_dir + \
                "/conversations/" + project.name + "-" + str(idx) + ".json"
            llm_wrapper: LLMWrapperInterface = prepare_conversation_wrapper(llm_wrapper_logpath)
            function = Function(lizard_result, project,
                                llm_wrapper, prompt_strategy)

            improve_function(function, improved_functions +
                                disregarded_functions, verification_strategy)

            get_logger().info("Function successfully improved")
            input("Press Enter to continue")
            function.apply_changes_to_target()
            improved_functions.append(function)
            save_git_diff_patch(repo, function, log_dir, idx)
            consecutive_exception_count = 0

        except NotImprovableException as e:
            get_logger().info("Disregarding function due to unsatisfactory " + e.reason)
            input("Press Enter to continue")
            function.restore_original_code()
            disregarded_functions.append(function)

        except BaseException as e:
            ++consecutive_exception_count
            get_logger().error(e)

            if consecutive_exception_count >= 3:
                raise e

            function.restore_original_code()
            disregarded_functions.append(function)

        finally:
            old_prj_cc = original_avg_project_cc if idx == 0 else time_series[
                idx-1]['new_prj_avg_cc']
            new_prj_cc = compute_avg_cc_for_project(
                project.dirty_path + project.code_dir)
            sent_tokens = llm_wrapper.sent_tokens_count
            received_tokens = llm_wrapper.received_tokens_count

            get_logger().info("Old CC of function: " + str(function.old_cc))
            get_logger().info("New CC of function: " + str(function.new_cc))
            get_logger().info("Old CC of project: " + str(old_prj_cc))
            get_logger().info("New CC of project: " + str(new_prj_cc))
            get_logger().info("LLM-processed tokens: " + str(sent_tokens + received_tokens))

            entry: TimeEntry = {
                'iteration': idx,
                'timestamp': datetime.now(timezone.utc),
                'function_file': function.relative_path,
                'function_name': function.lizard_result.long_name,
                'old_cc': function.old_cc,
                'new_cc': function.new_cc,
                'old_prj_avg_cc': old_prj_cc,
                'new_prj_avg_cc': new_prj_cc,
                'sent_tokens': sent_tokens,
                'received_tokens': received_tokens
            }
            time_series.append(entry)
            csv_path = log_dir + "/" + project.name + ".csv"
            save_time_entries_to_csv(csv_path, time_series)

if __name__ == "__main__":
    main()
