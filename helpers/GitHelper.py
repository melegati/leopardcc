from git import Repo
import os
from interfaces.Function import Function

def save_git_diff_patch(repo: Repo, function: Function, log_dir: str, idx: int):
    diff = repo.git.diff(function.relative_path)

    patch_dir = log_dir + '/patches'
    if not os.path.exists(patch_dir):
        os.makedirs(patch_dir)

    patch_file_path = patch_dir + '/' + str(idx) + '-' + function.lizard_result.name + '.diff'
    with open(patch_file_path, "w", encoding="utf-8") as patch_file:
        patch_file.write(diff)
    
    repo.git.add(function.relative_path)
    commit_message = 'apply patch for refactoring iteration ' + str(idx) + ' for fn ' +  function.lizard_result.name
    repo.index.commit(commit_message, skip_hooks=True)