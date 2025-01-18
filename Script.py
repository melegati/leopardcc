import datetime
from OpenAIWrapper import OpenAIWrapper
from projects.Expressjs import Expressjs
from projects.D3Shape import D3Shape
from prompt_strategies.ChoiEtAl import ChoiEtAl as ChoiEtAlPrompt
from verification_strategies.ChoiEtAl import ChoiEtAl as ChoiEtAlVerification
from Logger import get_logger, add_log_file_handler
from ProjectHelper import compute_cyclomatic_complexity, get_functions_sorted_by_complexity
from Refactorer import improve_function
from interfaces.Function import Function
from interfaces.NotImprovableException import NotImprovableException
import os


def prepare_log_dir() -> str:
    timestamp = filename = datetime.datetime.now(datetime.timezone.utc).strftime(
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

    try:
        for lizard_result in most_complex[:4]:
            # TODO (LS-2025-01-16): Create metrics reporter - How have metrics changed over time? How has avg_cc changed after each iteration?

            function = Function(lizard_result, project,
                                wrapper, prompt_strategy)
            try:
                improve_function(function, improved_functions +
                                 disregarded_functions, verification_strategy)

                get_logger().info("Function successfully improved")
                function.apply_changes_to_target()
                improved_functions.append(function)

            except NotImprovableException as e:
                get_logger().info("Function could not be improved, disregarding")
                function.restore_original_code()
                disregarded_functions.append(function)

    except BaseException as e:
        get_logger().error(e)


if __name__ == "__main__":
    main()
