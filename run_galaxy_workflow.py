#!/usr/bin/env python
"""run_galaxy_workflow

This script run workflows on galaxy instance using credentials.yml file provided.
The input data (barcodes.tsv, genes.tsv, matrix.mtx and gtf) files are upload from
provisioned locally in a directory. This scripts connects to galaxy instance and select the workflow of interest.

running syntax

python run_galaxy_workflow.py -C galaxy_credentials.yml -o output_dir -G 'embassy' -H 'scanpy_param_test' \
       -i inputs.yaml \
       -W Galaxy-Workflow-Scanpy_default_params.json \
       -P scanpy_param_pretty.json

File inputs.yaml must contain paths to all input labels in the workflow.
"""

import argparse
import logging
import os.path
import time
import yaml
from sys import exit
import pickle
import copy
import json
from bioblend.galaxy import GalaxyInstance


def get_args():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-C', '--conf',
                            required=True,
                            help='A yaml file describing the galaxy credentials')
    arg_parser.add_argument('-G', '--galaxy-instance',
                            default='embassy',
                            help='Galaxy server instance name')
    arg_parser.add_argument('-i', '--yaml-inputs-path',
                            required=True,
                            help='Path to Yaml detailing inputs')
    arg_parser.add_argument('-o', '--output-dir',
                            default=os.getcwd(),
                            help='Path to output directory')
    arg_parser.add_argument('-H', '--history',
                            default='',
                            required=True,
                            help='Name of the history to create')
    arg_parser.add_argument('-W', '--workflow',
                            default='scanpy_workflow_test',
                            required=True,
                            help='Workflow to run')
    arg_parser.add_argument('-P', '--parameters',
                            default='',
                            required=True,
                            help='scanpy parameters json')
    arg_parser.add_argument('--debug',
                            action='store_true',
                            default=False,
                            help='Print debug information')
    arg_parser.add_argument('-k', '--keep-histories',
                            action='store_true',
                            default=False,
                            help="Keeps histories created, they will be purged if not.")
    arg_parser.add_argument('-w', '--keep-workflow',
                            default=False,
                            help="Keeps workflow created, it will be purged if not.")
    args = arg_parser.parse_args()
    return args


def set_logging_level(debug=False):
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format='%(asctime)s - %(message)s',
        datefmt='%d-%m-%y %H:%M:%S')


def read_yaml_file(yaml_path):
    """
    Reads a YAML file safely.

    :param yaml_path:
    :return: dictionary object from YAML content.
    """
    stream = open(yaml_path, "r")
    return yaml.safe_load(stream)


def get_instance(conf, name='__default'):
    data = read_yaml_file(os.path.expanduser(conf))
    assert name in data, 'unknown instance'
    entry = data[name]
    if isinstance(entry, dict):
        return entry
    else:
        return data[entry]


def get_workflow_from_file(gi, workflow_file):
    import_workflow = [gi.workflows.import_workflow_from_local_path(file_local_path=workflow_file)]
    return import_workflow


def read_json_file(json_file_path):
    with open(json_file_path) as json_file:
        json_obj = json.load(json_file)
    return json_obj


def get_workflow_from_name(gi, workflow_name):
    wf = gi.workflows.get_workflows(name=workflow_name)
    return wf


def get_history_id(history_name, histories_obj):
    for hist_dict in histories_obj:
        if hist_dict['name'] == history_name:
            return hist_dict['id']


def get_workflow_id(wf):
    for wf_dic in wf:
        wf_id = wf_dic['id']
    return wf_id


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


def download_results(gi, history_id, output_dir, use_names=False):
    """
    Downloads results from a given Galaxy instance and history to a specified filesystem location.

    :param gi: galaxy instance object
    :param history_id: ID of the history from where results should be retrieved.
    :param output_dir: path to where result file should be written.
    :param use_names: whether to trust or not the internal Galaxy name for the final file name
    :return:
    """
    datasets = gi.histories.show_history(history_id,
                                         contents=True,
                                         visible=True, details='all')
    used_names = set()
    for dataset in datasets:
        if dataset['type'] == 'file':
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
                if use_names and ds_in_coll['object']['name'] is not None \
                        and ds_in_coll['object']['name'] not in used_names:
                    gi.datasets.download_dataset(ds_in_coll['object']['id'],
                                                 file_path=os.path.join(output_dir,ds_in_coll['object']['name']),
                                                 use_default_filename=False)
                    used_names.add(ds_in_coll['object']['name'])
                else:
                    gi.datasets.download_dataset(ds_in_coll['object']['id'],
                                                 file_path=output_dir,
                                                 use_default_filename=True)


def set_params(json_wf, param_data):
    params = {}
    for param_step_name in param_data:
        step_ids = (key for key, value in json_wf['steps'].items() if value['label'] == str(param_step_name))
        for step_id in step_ids:
            params.update({step_id: param_data[param_step_name]})
    return params


def load_input_files(gi, inputs, workflow, history):
    """
    Loads file in the inputs yaml to the Galaxy instance given. Returns
    datasets dictionary with names and histories.

    This setup currently doesn't support collections as inputs.

    Input yaml file should be formatted as:

    input_label_a:
      path: /path/to/file_a
      type:
    input_label_b:
      path: /path/to/file_b
      type:

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
        if step_data['label'] in inputs:
            upload_res = gi.tools.upload_file(path=inputs[step_data['label']]['path'], history_id=history['id'],
                                 file_name=step_data['label'],
                                 file_type=inputs[step_data['label']]['type'])
            inputs_for_invoke[step] = {
                    'id': upload_res['outputs'][0]['id'],
                    'src': 'hda'
                }
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
    Checks that paths exists in the local file system

    :param inputs: dictionary with inputs
    :return:
    """
    for input_key, input_content in inputs.items():
        if 'path' in input_content and not os.path.isfile(input_content['path']):
            raise ValueError("Input file {} does not exist for input label {}".format(input_content['path'], input_key))


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
                if tool['tool_shed_repository'] is not None:
                    ts_meta = tool['tool_shed_repository']
                    url = "https://{}/view/{}/{}/{}".format(ts_meta['tool_shed'], ts_meta['owner'], ts_meta['name'],
                                                            ts_meta['changeset_revision'])
                f.write("\t".join([label, tool['name'], tool['version'], url])+"\n")
                tools_dict.append(step['tool_id'])
                # tools_dict[step['tool_id']] = {'name': tool['name'], 'version': tool['version']}


def main():
    try:
        args = get_args()
        set_logging_level(args.debug)

        # Load workflows, inputs and parameters
        wf_from_json = read_json_file(args.workflow)
        param_data = read_json_file(args.parameters)
        inputs_data = read_yaml_file(args.yaml_inputs_path)

        # Validate data before talking to Galaxy
        validate_labels(wf_from_json, param_data)
        num_inputs = validate_input_labels(wf_json=wf_from_json, inputs=inputs_data)
        if num_inputs > 0:
            validate_file_exists(inputs_data)

        # Prepare environment
        logging.info('Prepare galaxy environment ...')
        ins = get_instance(args.conf, name=args.galaxy_instance)
        gi = GalaxyInstance(ins['url'], key=ins['key'])

        # Create new history to run workflow
        logging.info('Create new history to run workflow ...')
        history = gi.histories.create_history(name=args.history)

        # get saved workflow defined in the galaxy instance
        logging.info('Workflow setup ...')
        workflow = get_workflow_from_file(gi, workflow_file=args.workflow)
        workflow_id = get_workflow_id(wf=workflow)
        show_wf = gi.workflows.show_workflow(workflow_id)

        # upload dataset to history
        logging.info('Uploading dataset to history ...')
        if num_inputs > 0:
            datamap = load_input_files(gi, inputs=inputs_data,
                                   workflow=show_wf, history=history)
        else:
            datamap = {}
        # set parameters
        logging.info('Set parameters ...')
        params = set_params(wf_from_json, param_data)

        try:
            logging.info('Running workflow {}...'.format(show_wf['name']))
            results = gi.workflows.invoke_workflow(workflow_id=workflow_id,
                                                   inputs=datamap,
                                                   params=params,
                                                   history_name=(args.history + '_results'))
        except Exception as ce:
            logging.error("Failure when invoking invoke workflows: {}".format(str(ce)))
            print(str(ce))
            exit(1)

        logging.debug("About to start serialization...")
        try:
            res_file_path = os.path.join(args.output_dir, args.history + '_results.bin')
            binary_file = open(res_file_path, mode='wb')
            pickle.dump(results, binary_file)
            binary_file.close()
            logging.info("State serialized for recovery at {}".format(str(res_file_path)))
        except Exception as e:
            logging.error("Failed to serialize (skipping)... {}".format(str(e)))

        # Produce tool versions file
        produce_versions_file(gi=gi, workflow_from_json=wf_from_json,
                              path="{}/software_versions_galaxy.txt".format(args.output_dir))

        # wait for a little while and check if the status is ok
        logging.debug("Sleeping for 100 s now...")
        time.sleep(100)

        # get_run_state
        results_hid = gi.histories.show_history(results['history_id'])
        state = results_hid['state']

        # wait until the jobs are completed
        logging.debug("Got state: {}".format(state))
        while True:
            logging.debug("Got state: {}".format(state))
            if state == 'error':
                logging.error("Execution failed, see {}/histories/show_structure?__identifer={} for details. "
                              "You might require login with a particular user.".
                              format(gi.base_url, results_hid['id']))
                exit(1)
            elif state == 'ok':
                logging.info("Workflow finished successfully ok")
                break
            # TODO downloads could be triggered here to gain time.
            time.sleep(10)
            results_hid = gi.histories.show_history(results['history_id'])
            state = results_hid['state']

        # Download results
        logging.info('Downloading results ...')
        download_results(gi, history_id=results['history_id'],
                         output_dir=args.output_dir,
                         use_names=True)
        logging.info('Results available.')

        if not args.keep_histories:
            logging.info('Deleting histories...')
            gi.histories.delete_history(results['history_id'], purge=True)
            gi.histories.delete_history(history['id'], purge=True)
            logging.info('Histories purged...')

        if not args.keep_workflow:
            logging.info('Deleting workflow...')
            gi.workflows.delete_workflow(workflow_id=workflow_id)
            logging.info('Workflow deleted.')

        exit(0)
    except Exception as e:
        logging.error("Failed due to {}".format(str(e)))
        raise e


if __name__ == '__main__':
    main()



