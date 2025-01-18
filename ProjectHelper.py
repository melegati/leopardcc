import lizard  # type: ignore
from statistics import mean
from interfaces.TestError import TestError
from interfaces.ProjectInterface import ProjectInterface
from interfaces.LizardResult import LizardResult
from interfaces.Function import Function


def compute_cyclomatic_complexity(path: str) -> list[LizardResult]:
    extensions = lizard.get_extensions(extension_names=["io"])
    analysis = lizard.analyze(paths=[path], exts=extensions)

    functions = list()
    for file in list(analysis):
        for function in file.function_list:
            functions.append(function)

    return functions


def compute_avg_cc_for_project(path: str) -> float:
    functions = compute_cyclomatic_complexity(path)

    complexities: list[int] = []
    for fun in functions:
        complexities.append(fun.cyclomatic_complexity)

    avg_cc = mean(complexities)

    return avg_cc


def get_functions_sorted_by_complexity(functions: list[LizardResult]) -> list[LizardResult]:
    result = sorted(
        functions, key=lambda fun: fun.cyclomatic_complexity, reverse=True)
    return result


def is_new_function_improved(old_function: LizardResult, new_function: LizardResult) -> bool:
    old_cyclomatic = old_function.cyclomatic_complexity
    new_cyclomatic = new_function.cyclomatic_complexity
    return new_cyclomatic < old_cyclomatic


def get_most_complex_without_ignored(function: Function, functions_to_ignore: list[Function]) -> LizardResult:
    dirty_path_functions = compute_cyclomatic_complexity(function.dirty_path)
    sorted_functions = get_functions_sorted_by_complexity(dirty_path_functions)

    ignore_set = {
        fun.lizard_result.name for fun in functions_to_ignore if fun.lizard_result.filename == function.lizard_result.filename}
    fun_with_highest_cc: LizardResult | None = None
    for fun in sorted_functions:
        if fun.name not in ignore_set:
            fun_with_highest_cc = fun
            break

    if fun_with_highest_cc is None:
        raise BaseException("Refactored function " + function.lizard_result.name + " not found in file " +
                            function.dirty_path)

    return fun_with_highest_cc
