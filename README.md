# Galaxy workflow executor

This setup uses bioblend to run a Galaxy workflow through the cli:

- Inputs:
  - Galaxy workflow as JSON file (from share workflow -> download).
  - Parameters dictionary as JSON
  - Input files defined in YAML
  - Steps with allowed errors in YAML (optional)
  - History name (optional)

# Galaxy workflow

The workflow should be annotated with labels, ideally for all steps, but at least
for the steps where you want to be able to set parameters through the parameters
dictionary. It should be the JSON file resulting from Workflows (upper menu) -> Share workflow
(on the drop down menu of the workflow, in the workflow list) -> Download
(in the following screen).

# Parameters JSON

The parameters JSON file can be generated for an associated workflow using the script
generate_params_from_workflow.py

- Inputs:
    - Galaxy workflow as JSON file (from share workflow -> download)
    - Output directory path (optional)

The output parameters.JSON should follow the following structure:

```json
{
    "step_label_x": {
        "param_name": "value",
        ....
        "nested_param_name": {
            "n_param_name": "n_value",
            ....
            "x_param_name": "x_value"
        }

    },
    "step_label_x2": {
        ....
    },
    ....
    "other_galaxy_setup_params": { ... }
}
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

# Exit error codes

Currently produced error codes:

| Error code | Description |
|------------|-------------|
| 3          | Connection error during history deletion, this is not a critical error as most probably the history will get deleted by the server. A file named histories_to_check.txt is created in the working directory. Data will have been downloaded by then. |



