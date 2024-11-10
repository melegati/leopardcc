from ProjectInterface import ProjectInterface
import shutil
import subprocess
import re
import json


class Expressjs(ProjectInterface):
    @property
    def project_path(self):
        return '/media/lebkuchen/storage-disk/Repos/express'

    @property
    def code_dir(self):
        return '/lib'

    def after_copy_hook(self) -> None:
        project_copy_path = self.project_path + '-copy'
        node_modules_dir = '/node_modules'
        shutil.rmtree(project_copy_path + node_modules_dir)
        subprocess.run(['cd ' + project_copy_path +
                        ' && npm install'],
                       shell=True, capture_output=True, text=True, check=True)

    def measure_test_coverage(self, project_path: str):
        try:
            subprocess.run(['cd ' + project_path +
                            ' && npx nyc --exclude examples --exclude test --exclude benchmarks --reporter=json-summary npm test'],
                           shell=True, capture_output=True, text=True, check=True)
            with open(project_path + '/coverage/coverage-summary.json', "r") as coverage_summary:
                coverage_info = json.load(coverage_summary)

            coverage_info_cleansed = dict()
            for module in coverage_info:
                coverage_info_cleansed[module.replace(project_path, '')] = {
                    'coverage': coverage_info[module]}

            return coverage_info_cleansed

        except subprocess.CalledProcessError as e:
            print(f"An error occurred: {e}")
            return None

    def get_test_stacktrace(self, project_path: str) -> None | str:
        try:
            subprocess.run(['cd ' + project_path + ' && npm test'],
                           shell=True, capture_output=True, text=True, check=True)
            return None

        except subprocess.CalledProcessError as e:
            stdout_cleaned = re.sub('\[[0-9;]+[a-zA-Z]', '', e.stdout)
            stdout_no_esc = re.sub('\u001b', '', stdout_cleaned)
            stdout_filtered = re.sub(
                '(.*\n)+.*' + str(e.returncode) + ' failing', '', stdout_no_esc)
            return stdout_filtered
