from interfaces.PromptStrategyInterface import PromptStrategyInterface
from interfaces.LintError import LintError
from interfaces.TestError import TestError


class Melegati(PromptStrategyInterface):
    """Prompts adapted to JavaScript, taken from Choi, Jinsu et al. 2024: 'Iterative Refactoring of Real-World Open-Source Programs with Large Language Models'"""

    @property
    def name(self):
        return "Melegati"
    
    def initial_prompt(self, code: str) -> str:

        prompt = """```javascript
        {code}
        ```
        Refactor the provided javascript method to reduce its cyclomatic complexity.
        If possible, modularize it by extracting methods, creating helping functions and simplifying complex conditional statements.
        You can assume that the given method is functionally correct. Ensure that you do not alter
        the external behavior of the method, maintaining both syntactic and semantic correctness.
        You should keep the code style consistent with the original code considering that the output will analyzed by a linter. 
        Provide the javascript method within a code block. Avoid using natural language explanations.
        """.format(code=code)

        return prompt

    def linting_explanation_prompt(self, errors: list[LintError]) -> str:
        messages = map(lambda error: "Error: {message} \nViolated rule: {rule}\nErroneous code: {code}".format(
            message=error['message'], rule=error['rule_id'], code=error['erroneous_code']), errors)
        message_stack = '\n\n'.join(messages)

        prompt = """The refactored JavaScript method you provided does not pass the linter check. 
        You should keep the code style consistent with the original code. 
        The linting messages and the respective code look like:
        ```
        {message_stack}
        ```
        Explain why your code does not pass the linter check.
        """.format(message_stack=message_stack)

        return prompt

    def linting_fix_prompt(self) -> str:
        prompt = """Fix your method by utilizing the linting messages, the erroneous code,
        your explanation and the original method. Provide the javascript method within a code block.
        Do not explain anything in natural language."""

        return prompt

    def test_explanation_prompt(self, errors: list[TestError], test_cases: list[str]) -> str:
        stacks = map(lambda error: "{expectation}: {message_stack}".format(
            expectation=error['expectation'], message_stack=error['message_stack']), errors)
        stack_united = '\n\n'.join(list(stacks))
        test_cases_united = '\n\n'.join(test_cases)

        prompt = """The refactored JavaScript method you provided does not pass the test suite.
        The error messages and the call stack look like:
        ```
        {message_stack}
        ```
        Failing test(s) looks like:
        ```
        {tests}
        ```
        Explain why your code does not pass the unit tests.""".format(message_stack=stack_united, tests=test_cases_united)

        return prompt

    def test_fix_prompt(self) -> str:
        prompt = """Fix your method by utilizing the error message, the call stack, the failing test,
        your explanation and the original method. Provide the javascript method within a code block.
        Do not explain anything in natural language."""

        return prompt

    def better_improvement_explanation_prompt(self) -> str:
        prompt = """The refactored Javascript method you provided did not have its cyclomatic complexity reduced.
        Identify the section that can be modularized in the refactored method, such as by extracting methods, or conditional statements that can be simplified."""

        return prompt

    def better_improvement_fix_prompt(self) -> str:
        prompt = """Please rectify the refactored Javascript method to reduce its cyclomatic complexity by
        utilizing information about the section that can be modularized, including possible refactored methods or conditional statements that can be simplified.
        The method you provide should be semantically identical to the original method.
        Provide the full implementation of the improved Javascript method within a code block.
        Avoid providing explanations in natural language."""

        return prompt
