import datetime
from OpenAIWrapper import OpenAIWrapper
from projects.Expressjs import Expressjs
from projects.D3Shape import D3Shape
from prompt_strategies.ChoiEtAl import ChoiEtAl
from Logger import get_logger, add_log_file_handler
from ProjectHelper import compute_cyclomatic_complexity, get_most_complex_functions
from Function import improve_function
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
    strategy = ChoiEtAl()

    original_path = project.project_path
    code_dir = project.code_dir

    log_dir = prepare_log_dir()
    add_log_file_handler(log_dir + "/log.txt")

    wrapper = prepare_conversation_wrapper(log_dir)

    complexity_info = compute_cyclomatic_complexity(original_path + code_dir)
    most_complex = get_most_complex_functions(complexity_info)[0]

    try:
        improve_function(most_complex, wrapper, project, strategy)

    except BaseException as e:
        get_logger().error(e)


if __name__ == "__main__":
    main()
