from interfaces.LizardResult import LizardResult
from interfaces.Function import Function
from helpers.LizardHelper import extract_function_code, compute_cyclomatic_complexity, get_functions_sorted_by_complexity

# TODO (LS-2025-01-19): Try finding better name/place for this code


def __find_first_function_that_is_not_ignored__(functions: list[LizardResult], code_snippets_to_ignore: set[str]) -> LizardResult | None:
    for fun in functions:
        code = extract_function_code(fun)
        for snippet in code_snippets_to_ignore:
            if code != snippet and code not in snippet:
                return fun

    return None


def get_most_complex_without_ignored(function: Function, functions_to_ignore: list[Function]) -> LizardResult:
    dirty_path_functions = compute_cyclomatic_complexity(function.dirty_path)
    sorted_functions = get_functions_sorted_by_complexity(dirty_path_functions)

    code_snippets_to_ignore = {
        fun.current_code_in_dirty for fun in functions_to_ignore if fun.lizard_result.filename == function.lizard_result.filename}

    fun_with_highest_cc = __find_first_function_that_is_not_ignored__(
        sorted_functions, code_snippets_to_ignore)

    if fun_with_highest_cc is None:
        raise BaseException("Refactored function " + function.lizard_result.name + " not found in file " +
                            function.dirty_path)

    return fun_with_highest_cc
