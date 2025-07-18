from datetime import datetime, timezone
from llm_wrappers.OpenAIWrapper import OpenAIWrapper, TiktokenTokenCounter, GoogleTokenCounter
from prompt_strategies.ChoiEtAl import ChoiEtAl as ChoiEtAlPrompt
from prompt_strategies.Scheibe import Scheibe
from verification_strategies.ChoiEtAl import ChoiEtAl as ChoiEtAlVerification
from util.Logger import get_logger, add_log_file_handler, reset_logger
from util.CSVWriter import save_time_entries_to_csv
from helpers.LizardHelper import compute_cyclomatic_complexity, get_functions_sorted_by_complexity, compute_avg_cc
from helpers.GitHelper import save_git_diff_patch
from Refactorer import improve_function
from interfaces.Function import Function
from interfaces.LizardResult import LizardResult
from interfaces.NotImprovableException import NotImprovableException
from interfaces.LlmWrapperInterface import LLMWrapperInterface
from interfaces.ProjectInterface import ProjectInterface
from interfaces.PromptStrategyInterface import PromptStrategyInterface
from interfaces.VerificationStrategyInterface import VerificationStrategyInterface
import os
from interfaces.TimeSeriesEntry import TimeEntry, Result
from git import Repo
import traceback
import argparse
import importlib.util
import re

def prepare_log_dir(project_name: str) -> str:
    timestamp = filename = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d-%H-%M-%S")
    log_dir = "logs/" + timestamp + "-" + project_name
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    return log_dir


def prepare_openai_wrapper(model: str, log_path: str) -> LLMWrapperInterface:
    with open('openai-key.txt', "r", encoding="utf-8") as key_file:
        api_key = key_file.read()

    llm_wrapper = OpenAIWrapper(
        api_key=api_key,
        log_path=log_path,
        token_counter=TiktokenTokenCounter(model),
        model=model)

    return llm_wrapper

def prepare_google_wrapper(model: str, log_path: str) -> LLMWrapperInterface:
    with open('google-key.txt', 'r', encoding='utf-8') as key_file:
        api_key = key_file.read()
    
    llm_wrapper = OpenAIWrapper(
        api_key = api_key,
        log_path = log_path,
        token_counter=GoogleTokenCounter(model, api_key),
        model = model,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )

    return llm_wrapper

def get_model_wrapper(model: str, log_path: str) -> LLMWrapperInterface:
    if model in ['gpt-4o-mini']:
        return prepare_openai_wrapper(model, log_path)
    elif model in ['gemini-2.0-flash-001']:
        return prepare_google_wrapper(model, log_path)
    raise "Unknown model."

def create_time_series_entry(function: Function, llm_wrapper: LLMWrapperInterface, 
                            idx: int, time_series: list[TimeEntry], result: Result,
                            prompt_strategy: PromptStrategyInterface,
                            verification_strategy: VerificationStrategyInterface) -> TimeEntry:
    
    project = function.project
    
    if idx == 1:
        old_functions = compute_cyclomatic_complexity(project.path + project.code_dir)
        original_avg_project_cc = compute_avg_cc(old_functions)
        
        old_prj_cc = original_avg_project_cc
        old_fn_count = len(old_functions)
        old_avg_nloc = sum(fun.nloc for fun in old_functions) / len(old_functions)
    else:
        old_prj_cc = time_series[idx-2]['new_prj_avg_cc']
        old_fn_count = time_series[idx-2]['new_fn_count']
        old_avg_nloc = time_series[idx-2]['new_avg_nloc']


    new_functions = compute_cyclomatic_complexity(project.target_path + project.code_dir)
    new_prj_cc = compute_avg_cc(new_functions)
    new_fn_count = len(new_functions)
    new_avg_nloc = sum(fun.nloc for fun in new_functions) / len(new_functions)
    
    sent_tokens = llm_wrapper.sent_tokens_count
    received_tokens = llm_wrapper.received_tokens_count

    entry: TimeEntry = {
        'iteration': idx,
        'project': project.name,
        'prompt_strategy': prompt_strategy.name,
        'verification_strategy': verification_strategy.name,
        'model': function.llm_wrapper.model,
        'timestamp': datetime.now(timezone.utc),
        'function_file': function.relative_path,
        'function_name': function.lizard_result.long_name,
        'old_cc': function.old_cc,
        'new_cc': function.new_cc,
        'old_prj_avg_cc': old_prj_cc,
        'new_prj_avg_cc': new_prj_cc,
        'old_fn_count': old_fn_count,
        'new_fn_count': new_fn_count,
        'old_avg_nloc': old_avg_nloc,
        'new_avg_nloc': new_avg_nloc,
        'sent_tokens': sent_tokens,
        'received_tokens': received_tokens,
        'result': result
    }
    return entry

def has_overlapping_function_already_improved(improved_functions: list[Function], lizard_result: LizardResult) -> bool:

    if len(improved_functions) == 0: return False

    improved_functions_on_the_same_file = list(filter(lambda f: f.lizard_result.filename == lizard_result.filename, improved_functions))

    if len(improved_functions_on_the_same_file) > 0:
        for prev_improved_function in improved_functions_on_the_same_file:
            if prev_improved_function.contains_lines(lizard_result.start_line, lizard_result.end_line):
                return True
    return False

def main(project: ProjectInterface,
         prompt_strategy: PromptStrategyInterface = ChoiEtAlPrompt(),
         verification_strategy: VerificationStrategyInterface = ChoiEtAlVerification(),
         model: str = "gpt-4o-mini") -> None:

    reset_logger()
    log_dir = prepare_log_dir(project.name)
    add_log_file_handler(log_dir + "/log.txt")

    get_logger().info("Refactoring project " + project.name)
    get_logger().info("LLM: " + model)
    get_logger().info("Prompt strategy: " + prompt_strategy.name)
    get_logger().info("Verification strategy: " + verification_strategy.name)

    complexity_info = compute_cyclomatic_complexity(project.path + project.code_dir)
    most_complex = get_functions_sorted_by_complexity(complexity_info)

    improved_functions: list[Function] = list()
    disregarded_functions: list[Function] = list()

    repo = Repo(project.target_path)

    time_series: list[TimeEntry] = []
    
    consecutive_exception_count = 0
    was_keyboard_interrupt_raised = False
    idx = 0
    for lizard_result in most_complex:

        if idx >= 20:
            break

        if has_overlapping_function_already_improved(improved_functions, lizard_result):
            get_logger().info("Ignoring function " + lizard_result.long_name +
                                " from file " + function.relative_path +
                                " because overlapping function has already been improved.")
            continue

        idx = idx + 1
        result: Result | None = None
        try:
            llm_wrapper_logpath = log_dir + \
                "/conversations/" + project.name + "-" + str(idx) + ".json"
            llm_wrapper: LLMWrapperInterface = get_model_wrapper(model, llm_wrapper_logpath)
            function = Function(lizard_result, project,
                                llm_wrapper, prompt_strategy)
            get_logger().info("Refactoring function #" + str(idx) + 
                                ": " + lizard_result.long_name +
                                " from file " + function.relative_path +
                                " with CC: " + str(function.old_cc))

            improve_function(function, verification_strategy)

            result = 'success'
            get_logger().info("Function successfully improved")
            function.apply_changes_to_target()
            improved_functions.append(function)
            save_git_diff_patch(repo, function, log_dir, idx)
            consecutive_exception_count = 0

        except NotImprovableException as e:
            get_logger().info("Disregarding function due to " + e.reason)
            result = e.reason
            function.restore_original_code()
            disregarded_functions.append(function)

        except KeyboardInterrupt:
            was_keyboard_interrupt_raised = True
            raise

        except BaseException as e:
            ++consecutive_exception_count
            get_logger().error(e)
            get_logger().error(traceback.format_exc())
            get_logger().info("Disregarding function due to other error")

            if consecutive_exception_count >= 3:
                raise e

            function.restore_original_code()
            disregarded_functions.append(function)

        finally:
            if not was_keyboard_interrupt_raised:
                entry = create_time_series_entry(function=function, llm_wrapper=llm_wrapper, 
                                                idx=idx, time_series=time_series, 
                                                result=result if result is not None else 'other error',
                                                prompt_strategy=prompt_strategy,
                                                verification_strategy=verification_strategy)
                time_series.append(entry)
                csv_path = log_dir + "/" + project.name + ".csv"
                save_time_entries_to_csv(csv_path, time_series)

                get_logger().info("Old CC of function: " + str(entry['old_cc']))
                get_logger().info("New CC of function: " + str(entry['new_cc']))
                get_logger().info("Old avg CC of project: " + str(entry['old_prj_avg_cc']))
                get_logger().info("New avg CC of project: " + str(entry['new_prj_avg_cc']))
                get_logger().info("LLM-processed tokens: " + str(entry['sent_tokens'] 
                                    + entry['received_tokens']))
            


def read_args():

    parser = argparse.ArgumentParser()

    parser.add_argument("--project", required=True, type=str)
    parser.add_argument("--project-folder", type=str, default="projects")
    parser.add_argument("--prompt-strategy", type=str, choices=['ChoiEtAl', 'Scheibe', 'Melegati'], default='ChoiEtAl')
    parser.add_argument("--model", type=str, choices=['gpt-4o-mini', 'gemini-2.0-flash-001'], default='gpt-4o-mini')

    return parser.parse_args()


def get_class(folder, className):
    path = os.path.join(folder, f"{className}.py")
    spec = importlib.util.spec_from_file_location(className, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ProjectClass = getattr(module, re.sub("-", "_", className[:-3] if className.endswith(".py") else className))
    return ProjectClass

if __name__ == "__main__":
    args = read_args()

    projectClass = get_class(args.project_folder, args.project)
    promptStrategyClass = get_class('prompt_strategies', args.prompt_strategy)

    main(project=projectClass(), prompt_strategy=promptStrategyClass(), model=args.model)