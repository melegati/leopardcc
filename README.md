# Requirements

Ollama is required to run GPT OSS.

An OpenAI api key is required to run GPT 4o-mini. It should be placed in a file called ``openai-key.txt'' in the root folder of the repository.

To install the required packages, run:

```
pip install -r requirements.txt
```

You will need all the repositories locally. The repositories and respective commits are described in the repos.txt file.
You can use the following script to perform a shallow clone (just the head) of all projects at the commit we used:

```
./clone_repos.sh
```

# Running

You can run one specific case using:

```
python Script.py --project=<project_name> --prompt-strategy=<ChoiEtAl|Ours> --model=<model_name> [--reasoning-effort=<reasoning_effort>] [--iterations=<number,default:20>]
```

You can run the following to know the list of configured models:

```
python Script.py --help
```

You can also run an experiment in a specific folder containing a experiment.yml file running the following:

```
python experiment_runner.py <experiment_folder>
```

The experiments included in the paper are available in the folders:

```
experiments/choi_gpt_4o_mini_5runs
experiments/choi_vs_ours_gpt_4o_mini
experiments/ours_gpt_4o_mini_vs_gpt_oss_low
experiments/ours_gpt_oss_low_vs_gpt_oss_high
```