from OpenAIWrapper import OpenAIWrapper
from .ProjectInterface import ProjectInterface
from .PromptStrategyInterface import PromptStrategyInterface
from .LizardResult import LizardResult
from .LintError import LintError
from .TestError import TestError
from helpers.LizardHelper import extract_function_code


def __patch_code__(path: str, old_code: str, new_code: str) -> None:
    with open(path, 'r') as file:
        filedata = file.read()

    filedata = filedata.replace(old_code, new_code)

    with open(path, 'w') as file:
        file.write(filedata)


def __remove_code_block_backticks__(code: str) -> str:
    no_backticks = code.replace("```javascript\n", "").replace("\n```", "")
    return no_backticks


def __get_test_cases_from_errors__(errors: list[TestError], project: ProjectInterface) -> list[str]:
    test_cases: list[str] = []
    for error in errors:
        test_case = project.get_test_case(error)
        if test_case == None:
            continue
        test_cases.append(str(test_case))

    return test_cases


class Function:
    def __init__(self, lizard_result: LizardResult, project: ProjectInterface, wrapper: OpenAIWrapper, strategy: PromptStrategyInterface):
        self.lizard_result = lizard_result
        self.wrapper = wrapper
        self.strategy = strategy

        self.__old_cc__ = lizard_result.cyclomatic_complexity
        self.__new_cc__ = self.__old_cc__

        self.project = project
        self.original_path = lizard_result.filename
        self.dirty_path = lizard_result.filename.replace(
            project.path, project.dirty_path)
        self.target_path = lizard_result.filename.replace(
            project.path, project.target_path)

        code = extract_function_code(lizard_result)
        self.history: list[str] = [code]

    @property
    def old_cc(self) -> int:
        return self.__old_cc__

    @property
    def new_cc(self) -> int:
        return self.__new_cc__

    @new_cc.setter
    def new_cc(self, value):
        self.__new_cc__ = value

    @property
    def current_code_in_dirty(self) -> str:
        return self.history[-1]

    def __apply_dirty_changes__(self, changed_code: str):
        self.history.append(changed_code)
        __patch_code__(self.dirty_path,
                       old_code=self.history[-2], new_code=self.history[-1])

    def __process_llm_code__(self, code: str) -> str:
        code_without_backticks = __remove_code_block_backticks__(code)
        lint_fixed_code = self.project.run_lint_fix(code_without_backticks)
        
        return lint_fixed_code

    def initial_refactor(self) -> None:
        prompt = self.strategy.initial_prompt(self.history[-1])

        llm_response_code = self.wrapper.send_message(prompt)
        postprocessed_code = self.__process_llm_code__(llm_response_code)

        self.__apply_dirty_changes__(postprocessed_code)

    def refactor_with_lint_errors(self, errors: list[LintError]) -> None:
        prompt = self.strategy.linting_explanation_prompt(errors)
        explanation = self.wrapper.send_message(prompt)

        prompt = self.strategy.linting_fix_prompt()
        llm_response_code = self.wrapper.send_message(prompt)
        postprocessed_code = self.__process_llm_code__(llm_response_code)

        self.__apply_dirty_changes__(postprocessed_code)

    def refactor_with_test_errors(self, errors: list[TestError]) -> None:
        top_errors = errors[:10]
        test_cases = __get_test_cases_from_errors__(top_errors, self.project)

        prompt = self.strategy.test_explanation_prompt(errors, test_cases)
        explanation = self.wrapper.send_message(prompt)

        prompt = self.strategy.test_fix_prompt()
        llm_response_code = self.wrapper.send_message(prompt)
        postprocessed_code = self.__process_llm_code__(llm_response_code)

        self.__apply_dirty_changes__(postprocessed_code)

    def refactor_for_better_improvement(self) -> None:
        prompt = self.strategy.better_improvement_explanation_prompt()
        self.wrapper.send_message(prompt)

        prompt = self.strategy.better_improvement_fix_prompt()
        llm_response_code = self.wrapper.send_message(prompt)
        postprocessed_code = self.__process_llm_code__(llm_response_code)

        self.__apply_dirty_changes__(postprocessed_code)

    def restore_original_code(self) -> None:
        __patch_code__(self.dirty_path,
                       old_code=self.history[-1], new_code=self.history[0])
        self.history.append(self.history[0])

    def apply_changes_to_target(self) -> None:
        __patch_code__(self.target_path,
                       old_code=self.history[0], new_code=self.history[-1])
