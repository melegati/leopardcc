from OpenAIWrapper import OpenAIWrapper
from Interfaces import PromptStrategyInterface, LintError, TestError


def __remove_code_block_backticks(code: str) -> str:
    no_backticks = code.replace("```javascript\n", "").replace("\n```", "")
    return no_backticks


def refactor_function(code: str, wrapper: OpenAIWrapper, strategy: PromptStrategyInterface) -> str:
    prompt = strategy.initial_prompt(code)

    improved_code = wrapper.send_message(prompt)
    code_without_backticks = __remove_code_block_backticks(improved_code)
    return code_without_backticks


def refactor_with_lint_errors(errors: list[LintError], wrapper: OpenAIWrapper, strategy: PromptStrategyInterface) -> str:
    prompt = strategy.linting_explanation_prompt(errors)
    explanation = wrapper.send_message(prompt)

    prompt = strategy.linting_fix_prompt()
    improved_code = wrapper.send_message(prompt)
    code_without_backticks = __remove_code_block_backticks(improved_code)
    return code_without_backticks


def refactor_with_test_errors(errors: list[TestError], test_cases: list[str], wrapper: OpenAIWrapper, strategy: PromptStrategyInterface) -> str:
    prompt = strategy.test_explanation_prompt(errors, test_cases)
    explanation = wrapper.send_message(prompt)

    prompt = strategy.test_fix_prompt()
    improved_code = wrapper.send_message(prompt)
    code_without_backticks = __remove_code_block_backticks(improved_code)
    return code_without_backticks


def refactor_for_better_improvement(wrapper: OpenAIWrapper, strategy: PromptStrategyInterface) -> str:
    prompt = strategy.better_improvement_explanation_prompt()
    wrapper.send_message(prompt)

    prompt = strategy.better_improvement_fix_prompt()
    improved_code = wrapper.send_message(prompt)
    code_without_backticks = __remove_code_block_backticks(improved_code)
    return code_without_backticks
