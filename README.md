[![PyPI version fury.io](https://badge.fury.io/py/galaxy-workflow-executor.svg)](https://pypi.python.org/pypi/galaxy-workflow-executor/)
[![Build Status](https://api.travis-ci.com/ebi-gene-expression-group/galaxy-workflow-executor.svg?branch=develop)](https://travis-ci.org/ebi-gene-expression-group/galaxy-workflow-executor)

# Galaxy workflow executor 0.2.2

This setup uses bioblend (0.12 - 0.13 tested) to run a Galaxy workflow through the CLI:

- Inputs:
  - Galaxy workflow with steps annotated with labels as JSON file (MUST be obtained in Galaxy UI from Share Workflow -> Download).
  - Parameters dictionary as YAML (JSON also supported). Supports both simple input parameters and tools parameters not exposed by simple input parameters.
  - Input files specified as paths or dataset IDs in a YAML file.
  - Steps with allowed errors specified in a YAML file (optional)
  - Name for a history to be created (optional)

# Galaxy workflow

The workflow should be annotated with labels, ideally for all steps, but at least
for the steps where you want to be able to set parameters through the parameters
dictionary. It should be the JSON file resulting from Workflows (upper menu) -> Share workflow
(on the drop down menu of the workflow, in the workflow list) -> Download
(in the following screen).

# Execution state

The setup will store the execution state during the run, so that if there are disconnection or errors, it can restart
following the progress of the same workflow. It stores the state by default in the working directory, in
`exec_state.pickle`. This might not be session proof: having a failure running workflow A, then trying to run a
subsequent workflow B you might get errors. So when switching running workflows, make sure to use either different
working directories or specify the path to the state path explicitly through `--state-file`. Please note that to specify
this for a new run, the file is not expected to exist.

The state file is deleted automatically on a successful execution.

# Parameters YAML

The parameters YAML file can be generated for a desired workflow by executing:

```
generate_params_from_workflow.py -C galaxy_credentials.yaml \
                            -G test_instance -o test \
                            -W wf.json
```

- Inputs:
    - Credentials file to a Galaxy instance (this file uses the same format as the one used by [parsec](https://parsec.readthedocs.io/en/latest/))
    - Name of the Galaxy instance among those listed in the credentials file (optional).
    - Galaxy workflow as JSON file (from share workflow -> download)
    - Output directory path (optional)

The output wf-parameters.yaml will follow the following structure:

```yaml
step_label_x:
   param_name: "value"
    ....
   nested_param_name:
        n_param_name: "n_value"
        ....
        x_param_name: "x_value"
step_label_x2:
    ....
....
other_galaxy_setup_params: { ... }
```

# Input files in YAML

It should point to the files in the file system, set a name (which needs to match
with a workflow input label) and file type (among those recognized by Galaxy).

The structure of the YAML file for inputs is:

```yaml
matrix:
  path: /path/to/E-MTAB-4850.aggregated_filtered_counts.mtx
  type: txt
genes:
  path: /path/to/E-MTAB-4850.aggregated_filtered_counts.mtx_rows
  type: tsv
barcodes:
  path: /path/to/E-MTAB-4850.aggregated_filtered_counts.mtx_cols
  type: tsv
gtf:
  dataset_id: fe139k21xsak
```

where in this example case the Galaxy workflow should have input labels called `matrix`,
`genes`, `barcodes` and `gtf`. The paths need to exist in the local file system, if `path` is set within an input. Alternatively to a path in the local file system, if the file is already on the Galaxy instance, the `dataset_id` of the file can be given instead, as shown for the `gtf` case here.

# Steps with allowed errors

This optional YAML file indicates the executor which steps are allowed to fail without the overal execution being considered
failed and hence retrieving result files anyway. This is to make room to the fact that on a production setup, there might
be border conditions on datasets that could produce acceptable failures.

The structure of the file relies on the labels for steps used in the workflow and parameters files

```yaml
step_label_x:
  - any
step_label_z:
  - 1
  - 43
```

The above example means that the step with label `step_label_x` can fail with any error code, whereas step with label
`step_label_z` will only be allowed to fail with codes 1 or 43 (specific error code handling is not yet implemented).

# Results

All workflow outputs that were marked in the workflow to be shown will be downloaded to the specified results directory,
hidden results will be ignored. Unless specified, histories (with its contents) and workflows will be deleted from the instance.

# Toy example

A simple example, which is used in the CI testing, can be seen and run locally through the
[run_tests_with_containers.sh](run_tests_with_containers.sh) script.

# Exit error codes

Currently produced error codes:

| Error code | Description |
|------------|-------------|
| 3          | Connection error during history deletion, this is not a critical error as most probably the history will get deleted by the server. A file named histories_to_check.txt is created in the working directory. Data will have been downloaded by then. |



