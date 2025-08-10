from interfaces.PromptStrategyInterface import PromptStrategyInterface
from interfaces.LintError import LintError
from interfaces.TestError import TestError


class Melegati(PromptStrategyInterface):
    """Prompts adapted to JavaScript and improved taken from Choi, Jinsu et al. 2024: 'Iterative Refactoring of Real-World Open-Source Programs with Large Language Models'"""

    def __init__(self):
        self.strategies_text = """Consider the following strategies that can be used to refactor the code: 
                                - Extract Function: Break complex functions into smaller, single-purpose ones
                                - Replace Nested Conditional with Guard Clauses: Reduce deep nesting by returning early
                                - Decompose Conditional: Break a complex conditional into simpler, named parts
                                - Consolidate Conditional Expression: Merge multiple related conditionals into one
                                - Consolidate Duplicate Conditional Fragments: Remove repeated branches in conditionals
                                - Replace Conditional with Polymorphism (or Strategy Pattern locally): Replace long if/else or switch with interchangeable behaviors
                                - Split Loop: Separate loops that handle multiple responsibilities into individual loops
                                - Remove Dead Code: Eliminate unused branches and conditions
                                - Introduce Explaining Variable: Assign parts of complex conditions to descriptive variables
                                - Replace Conditional with Lookup Table: Use an object or map instead of multiple if/switch cases"""

    @property
    def name(self):
        return "Melegati"
    
    def initial_prompt(self, code: str) -> str:

        prompt = """```javascript
{code}
```
Refactor the provided javascript method to reduce its cyclomatic and cognitive complexities.
{strategies}
You can assume that the given method is functionally correct. Ensure that you do not alter
the external behavior of the method, maintaining both syntactic and semantic correctness.
You should keep the code style consistent with the original code considering that the output will analyzed by a linter. 
You should keep the identation of the code consistent with the original one.
Provide the javascript method within a code block. Avoid using natural language explanations.
""".format(code=code, strategies=self.strategies_text)

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
Identify the section that can be improved in the refactored method.
{strategies}""".format(strategies=self.strategies_text)

        return prompt

    def better_improvement_fix_prompt(self) -> str:
        prompt = """Please rectify the refactored Javascript method to reduce its cyclomatic and cognitive complexities by
utilizing information about the section that can be improved.
{strategies}
The method you provide should be semantically identical to the original method.
Provide the full implementation of the improved Javascript method within a code block.
Avoid providing explanations in natural language.""".format(strategies=self.strategies_text)

        return prompt
