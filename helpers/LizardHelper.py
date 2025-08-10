import lizard  # type: ignore
import re
from statistics import mean
from functools import reduce
import operator
from interfaces.TestError import TestError
from interfaces.ProjectInterface import ProjectInterface
from interfaces.LizardResult import LizardResult

def compute_cyclomatic_complexity(path: str) -> list[LizardResult]:
    extensions = lizard.get_extensions(extension_names=["io"])
    analysis = lizard.analyze(paths=[path], exts=extensions)

    functions = list()
    for file in list(analysis):
        for function in file.function_list:
            functions.append(function)

    return functions


def compute_avg_cc(functions: list[LizardResult]) -> float:
    complexities: list[int] = []
    for fun in functions:
        complexities.append(fun.cyclomatic_complexity)

    avg_cc = mean(complexities)

    return avg_cc


def get_functions_sorted_by_complexity(functions: list[LizardResult]) -> list[LizardResult]:
    result = sorted(
        functions, key=lambda fun: fun.cyclomatic_complexity, reverse=True)
    return result

def add_function_keyword(code):
    # This regex matches method definitions inside classes
    method_pattern = re.compile(r'^\s*(\w+)\s*\((.*?)\)\s*\{', re.MULTILINE)

    def replacer(match):
        method_name = match.group(1)
        args = match.group(2)
        return f'function {method_name}({args})' + ' {'

    # Replace each method definition with "function <name>(<args>) {"
    updated_code = method_pattern.sub(replacer, code)
    return updated_code

def compute_cc_from_code(code: str) -> int:
    analysis = lizard.analyze_file.analyze_source_code("Test.js", code)
    functions = analysis.function_list
    if len(functions) == 0:
        print("failed to calculate CC, trying to add function in front of the code")
        analysis = lizard.analyze_file.analyze_source_code("Test.js", add_function_keyword(code))
        functions = analysis.function_list
    complexities = list(fun.cyclomatic_complexity for fun in functions)
    complexities_sorted = sorted(complexities, reverse=True)

    try:
        highest_complexity = complexities_sorted[0]
    except IndexError as e:
        print("Index error while measuring cc, caused by the following code: ")
        print(code)
        raise

    return highest_complexity

def extract_function_code(function: LizardResult) -> str:
    with open(function.filename) as file:
        code = file.readlines()
    function_lines = code[function.start_line - 1:function.end_line]
    function_code = reduce(operator.add, function_lines)
    # code_without_leading_spaces = function_code.lstrip()
    # return code_without_leading_spaces
    return function_code
