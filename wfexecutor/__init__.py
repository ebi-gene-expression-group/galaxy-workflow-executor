import logging
import os
import time

import os.path

from collections.abc import Mapping
import yaml
import json
import pickle


def get_instance(conf, name='__default'):
    data = read_yaml_file(os.path.expanduser(conf))
    assert name in data, 'unknown instance'
    entry = data[name]
    if isinstance(entry, dict):
        return entry
    else:
        return data[entry]


def read_json_file(json_file_path):
    with open(json_file_path) as json_file:
        json_obj = json.load(json_file)
    return json_obj


def read_yaml_file(yaml_path):
    """
    Reads a YAML file safely.

    :param yaml_path:
    :return: dictionary object from YAML content.
    """
    stream = open(yaml_path, "r")
    return yaml.safe_load(stream)


def get_workflow_from_file(gi, workflow_file):
    import_workflow = [gi.workflows.import_workflow_from_local_path(file_local_path=workflow_file)]
    return import_workflow


def get_workflow_from_name(gi, workflow_name):
    wf = gi.workflows.get_workflows(name=workflow_name)
    return wf


def get_workflow_id(wf):
    for wf_dic in wf:
        wf_id = wf_dic['id']
    return wf_id


def get_history_id(history_name, histories_obj):
    for hist_dict in histories_obj:
        if hist_dict['name'] == history_name:
            return hist_dict['id']


def get_input_data_id(file, wf):
    file_name = os.path.splitext(file)[0]
    for id in wf['inputs']:
        if wf['inputs'][id]['label'] == file_name:
            input_id = id
    return input_id


def get_run_state(gi, results):
    results_hid = gi.histories.show_history(results['history_id'])
    state = results_hid['state']
    return state


def download_results(gi, history_id, output_dir, allowed_error_states, use_names=False):
    """
    Downloads results from a given Galaxy instance and history to a specified filesystem location.

    :param gi: galaxy instance object
    :param history_id: ID of the history from where results should be retrieved.
    :param output_dir: path to where result file should be written.
    :param allowed_error_states: dictionary with elements known to be allowed to fail.
    :param use_names: whether to trust or not the internal Galaxy name for the final file name
    :return:
    """
    datasets = gi.histories.show_history(history_id,
                                         contents=True,
                                         visible=True, details='all')
    used_names = set()
    for dataset in datasets:
        if dataset['type'] == 'file':
            if dataset['state'] == 'error' and dataset['id'] in allowed_error_states['datasets']:
                logging.info('Skipping download of failed {} as it is an allowed failure.'
                             .format(dataset['name']))
                continue
            if use_names and dataset['name'] is not None and dataset['name'] not in used_names:
                gi.datasets.download_dataset(dataset['id'], file_path=os.path.join(output_dir, dataset['name']),
                                             use_default_filename=False)
                used_names.add(dataset['name'])
            else:
                gi.datasets.download_dataset(dataset['id'],
                                             file_path=output_dir,
                                             use_default_filename=True)
        elif dataset['type'] == 'collection':
            for ds_in_coll in dataset['elements']:
                if ds_in_coll['object']['state'] == 'error' and ds_in_coll['object']['id'] in allowed_error_states['datasets']:
                    logging.info('Skipping download of failed {} as it is an allowed failure.'
                                 .format(ds_in_coll['object']['name']))
                    continue
                if use_names and ds_in_coll['object']['name'] is not None \
                        and ds_in_coll['object']['name'] not in used_names:
                    # TODO it fails here to download if it is in 'error' state
                    gi.datasets.download_dataset(ds_in_coll['object']['id'],
                                                 file_path=os.path.join(output_dir, ds_in_coll['object']['name']),
                                                 use_default_filename=False)
                    used_names.add(ds_in_coll['object']['name'])
                else:
                    gi.datasets.download_dataset(ds_in_coll['object']['id'],
                                                 file_path=output_dir,
                                                 use_default_filename=True)


def set_params(json_wf, param_data):
    """
    Associate parameters to workflow steps via the step label. The result is a dictionary
    of parameters that can be passed to invoke_workflow.

    :param json_wf:
    :param param_data:
    :return:
    """
    params = {}
    for param_step_name in param_data:
        step_ids = (key for key, value in json_wf['steps'].items() if value['label'] == str(param_step_name))
        for step_id in step_ids:
            params.update({step_id: param_data[param_step_name]})
        for param_name in param_data[param_step_name]:
            if '|' in param_name:
                logging.warning("Workflow using Galaxy <repeat /> "
                                "param. type for {} / {}. "
                                "Make sure that workflow has as many entities of that repeat "
                                "as they are being set in the parameters file.".format(param_step_name, param_name))
                break
    return params


def load_input_files(gi, inputs, workflow, history):
    """
    Loads file in the inputs yaml to the Galaxy instance given. Returns
    datasets dictionary with names and histories. It associates existing datasets on Galaxy given by dataset_id
    to the input where they should be used.

    This setup currently doesn't support collections as inputs.

    Input yaml file should be formatted as:

    input_label_a:
      path: /path/to/file_a
      type:
    input_label_b:
      path: /path/to/file_b
      type:
    input_label_c:
      dataset_id:
    input_label_d:
      collection_id:

    this makes it extensible to support
    :param gi: the galaxy instance (API object)
    :param inputs: dictionary of inputs as read from the inputs YAML file
    :param workflow: workflow object produced by gi.workflows.show_workflow
    :param history: the history object to where the files should be uploaded
    :return: inputs object for invoke_workflow
    """

    inputs_for_invoke = {}

    for step, step_data in workflow['inputs'].items():
        # upload file and record the identifier
        if step_data['label'] in inputs and 'path' in inputs[step_data['label']]:
            upload_res = gi.tools.upload_file(path=inputs[step_data['label']]['path'], history_id=history['id'],
                                              file_name=step_data['label'],
                                              file_type=inputs[step_data['label']]['type'])
            inputs_for_invoke[step] = {
                    'id': upload_res['outputs'][0]['id'],
                    'src': 'hda'
                }
        elif step_data['label'] in inputs and 'dataset_id' in inputs[step_data['label']]:
            inputs_for_invoke[step] = {
                'id': inputs[step_data['label']]['dataset_id'],
                'src': 'hda'
            }
        elif step_data['label'] in inputs and 'collection_id' in inputs[step_data['label']]:
            inputs_for_invoke[step] = {
                'id': inputs[step_data['label']]['collection_id'],
                'src': 'hdca'
            }
        elif step_data['label'] in inputs and not isinstance(inputs[step_data['label']], Mapping):
            # We are in the presence of a simple parameter input
            inputs_for_invoke[step] = inputs[step_data['label']]
        else:
            raise ValueError("Label '{}' is not present in inputs yaml".format(step_data['label']))

    return inputs_for_invoke


def validate_labels(wf_from_json, param_data, exit_on_error=True):
    """
    Checks that all workflow steps have labels (although if not the case, it will only
    warn that those steps won't be configurable for parameters) and that all step labels
    in the parameter files exist in the workflow file. If the second case is not true,
    the offending parameter is shown and the program exists.

    :param wf_from_json:
    :param param_data:
    :param exit_on_error:
    :return:
    """
    step_labels_wf = []
    for step_id, step_content in wf_from_json['steps'].items():
        if step_content['label'] is None:
            logging.warning("Step No {} in json workflow does not have a label, parameters are not mappable there.".format(step_id))
        step_labels_wf.append(step_content['label'])
    errors = 0
    for step_label_p, params in param_data.items():
        if step_label_p not in step_labels_wf:
            if exit_on_error:
                raise ValueError(
                    " '{}' parameter step label is not present in the workflow definition".format(step_label_p))
            logging.error("{} parameter step label is not present in the workflow definition".format(step_label_p))
            errors += 1
    if errors == 0:
        logging.info("Validation of labels: OK")


def validate_input_labels(wf_json, inputs):
    """
    Check that all input datasets in the workflow have labels, and that those labels are available in the inputs yaml.
    Raises an exception if those cases are not fulfilled.

    :param wf_json:
    :param inputs:
    :return: the number of input labels.
    """

    number_of_inputs = 0
    for step, step_content in wf_json['steps'].items():
        if step_content['type'] == 'data_input':
            number_of_inputs += 1
            if step_content['label'] is None:
                raise ValueError("Input step {} in workflow has no label set.".format(str(step)))

            if step_content['label'] not in inputs:
                raise ValueError("Input step {} label {} is not present in the inputs YAML file provided."
                                 .format(str(step), step_content['label']))
    return number_of_inputs


def validate_file_exists(inputs):
    """
    Checks that paths exists in the local file system.

    :param inputs: dictionary with inputs
    :return:
    """
    for input_key, input_content in inputs.items():
        if 'path' in input_content and not os.path.isfile(input_content['path']):
            raise ValueError("Input file {} does not exist for input label {}".format(input_content['path'], input_key))


def validate_dataset_id_exists(gi, inputs):
    """
    Checks that dataset_id exists in the Galaxy instance when dataset_id are specified. Raises an error if the dataset
    id doesn't exists in the instance.

    :param gi:
    :param inputs:
    :return:
    """
    warned = False
    for input_key, input_content in inputs.items():
        if 'dataset_id' in input_content:
            ds_in_instance = gi.datasets.show_dataset(dataset_id=input_content['dataset_id'])
            if not warned:
                logging.warning("You are using direct dataset identifiers for inputs, "
                                "this execution is not portable accross instances.")
                warned = True
            if not isinstance(ds_in_instance, dict):
                raise ValueError("Input dataset_id {} does not exist in the Galaxy instance."
                                 .format(input_content['dataset_id']))


def completion_state(gi, history, allowed_error_states, wait_for_resubmission=True):
    """
    Checks whether the history is in error state considering potential acceptable error states
    in the allowed error states definition.

    :param wait_for_resubmission:
    :param gi: The galaxy instance connection
    :param history:
    :param allowed_error_states: dictionary containing acceptable error states for steps
    :return: two booleans, error_state and completed
    """

    # First easy check for error state if there are no allowed errors
    error_state = len(allowed_error_states['tools']) == 0 and history['state_details']['error'] > 0

    # If there are allowed error states, check details
    if not error_state:
        for dataset_id in history['state_ids']['error']:
            # Sometimes transient error states will be found for jobs that are in the process
            # of being resubmitted. This part accounts for that, waiting for the state to go back
            # from error.
            if wait_for_resubmission:
                # We have seen jobs circling from error to running again in lapses of around 10 seconds
                # at the most, so we wait for conservative period. This could be improved later.
                logging.info("Waiting 20 sec to check if the job gets re-submitted")
                time.sleep(20)
                ds = gi.datasets.show_dataset(dataset_id)
                if not ds['resubmitted']:
                    logging.info("Job was not resubmitted")
                    error_state = True
                elif ds['state'] != 'error':
                    logging.info("Job was resubmitted and is not in error any more...")
                else:
                    logging.info("Job was resubmitted at some point, but still shows to be in error state...")
                    error_state = True
            else:
                error_state = True

            if error_state:
                if dataset_id in allowed_error_states['datasets']:
                    # if the dataset was already in allowed error states, then we know it doesn't represent
                    # a complete workflow execution error
                    error_state = False
                    continue
                dataset = gi.datasets.show_dataset(dataset_id)
                job = gi.jobs.show_job(dataset['creating_job'])
                if job['tool_id'] in allowed_error_states['tools']:
                    allowed_error_states['datasets'].add(dataset_id)
                    error_state = False
                    # TODO decide based on individual error codes.
                    continue
                # The tool has failed and it wasn't allowed to fail, we signal this and we stop checking for errored
                # datasets. This will signal the setup that we are in a terminal error state
                logging.info("Tool {} is not marked as allowed to fail, but has failed.".format(job['tool_id']))
                break



    # We separate completion from errors, so a workflow might have completed with or without errors
    # (this includes allowed errors). We say the workflow is in completed state when all datasets are in states:
    # error, ok, paused or failed_metadata.
    terminal_states = ['error', 'ok', 'paused', 'failed_metadata']
    non_terminal_datasets_count = 0
    terminal_datasets_count = 0
    for state, count in history['state_details'].items():
        if state not in terminal_states:
            non_terminal_datasets_count += count
        if state in terminal_states:
            terminal_datasets_count += count

    # We add the terminal_datasets_count to avoid falling here when all job states are in zero.
    completed_state = (non_terminal_datasets_count == 0 and terminal_datasets_count > 0)

    if completed_state:
        # add all paused jobs to allowed_error_states or fail if jobs are paused that are not allowed
        for dataset_id in history['state_ids']['paused']:
            dataset = gi.datasets.show_dataset(dataset_id)
            job = gi.jobs.show_job(dataset['creating_job'])
            if job['tool_id'] in allowed_error_states['tools']:
                allowed_error_states['datasets'].add(dataset_id)
                # TODO decide based on individual error codes.
                continue
            logging.info("Tool {} is not marked as allowed to fail, but is paused due to a previous tool failure."
                         .format(job['tool_id']))
            error_state = True
        # display state of jobs in history:
        logging.info("Workflow run has completed, job counts per states are:")
        for state, count in history['state_details'].items():
            logging.info("{}: {}".format(state, count))

    return error_state, completed_state


def process_allowed_errors(allowed_errors_dict, wf_from_json):
    """
    Reads the input from allowed errors file and translates the workflow steps into tool identifiers that will be
    allowed to error out, either on all error codes (when "any" is available for the tool) or on specified error codes.

    :param wf_from_json:
    :param allowed_errors_dict: content from yaml file with definition of steps can fail.
    :return:
    """

    allowed_errors_state = {'tools': {}, 'datasets': set()}
    for step_id, step_content in wf_from_json['steps'].items():
        if step_content['label'] is not None and step_content['tool_id'] is not None:
            if step_content['label'] in allowed_errors_dict:
                allowed_errors_state['tools'][step_content['tool_id']] = allowed_errors_dict[step_content['label']]

    return allowed_errors_state

def produce_versions_file(gi, workflow_from_json, path):
    """
    Produces a tool versions file for the workflow run.

    :param gi:
    :param workflow_from_json:
    :param path: path where to save the versions file
    :return:
    """

    tools_dict = []

    with open(file=path, mode="w") as f:
        f.write("\t".join(["Analysis", "Software", "Version", "Citation"])+"\n")

        for key, step in sorted(workflow_from_json['steps'].items(), reverse=True):
            # Input steps won't have tool ids, and we only need each tool once.
            if step['tool_id'] is not None and step['tool_id'] not in tools_dict:
                tool = gi.tools.show_tool(step['tool_id'])
                label = step['label'] if step['label'] is not None else tool['name']
                url = ""
                if 'tool_shed_repository' in tool and tool['tool_shed_repository'] is not None:
                    ts_meta = tool['tool_shed_repository']
                    url = "https://{}/view/{}/{}/{}".format(ts_meta['tool_shed'], ts_meta['owner'], ts_meta['name'],
                                                            ts_meta['changeset_revision'])
                f.write("\t".join([label, tool['name'], tool['version'], url])+"\n")
                tools_dict.append(step['tool_id'])


class ExecutionState(object):

    wf_from_file = None
    datamap = None
    params = None
    results = None
    input_history = None

    def __init__(self, path):
        self.path = path

    @staticmethod
    def start(path):
        if os.path.isfile(path):
            try:
                with open(path, mode='rb') as d:
                    es = pickle.load(d)
                    if type(es) is ExecutionState:
                        return es
                    else:
                        logging.warning("The provided file {} does not have an ExecutionState object serialised".format(path))
            except Exception:
                logging.warning("Could not read serialized file {}.".format(path))
        return ExecutionState(path)

    def save_state(self):
        with open(self.path, mode='wb') as d:
            pickle.dump(self, d)
            
