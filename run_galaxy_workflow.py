#!/usr/bin/env python
"""run_galaxy_workflow

This script run workflows on galaxy instance using credentials.yml file provided.
The input data (barcodes.tsv, genes.tsv, matrix.mtx and gtf) files are upload from
provisioned locally in a directory. This scripts connects to galaxy instance and select the workflow of interest.

running syntax

python run_galaxy_workflow.py -C galaxy_credentials.yml -D E-MTAB-101 -I 'embassy' -H 'scanpy_param_test' -W Galaxy-Workflow-Scanpy_default_params.json -P scanpy_param_pretty.json

E-MTAB-101 the experiment directory contains barcodes.tsv, genes.tsv, matrix.mtx and gtf.gz
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
    arg_parser.add_argument('-D', '--experimentDir',
                            default='',
                            required=True,
                            help='Path to experiment directory folder')
    arg_parser.add_argument('-I', '--instance',
                            default='embassy',
                            help='Galaxy server instance name')
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
    args = arg_parser.parse_args()
    return args


def set_logging_level(debug=False):
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format= '%(asctime)s - %(message)s',
        datefmt='%d-%m-%y %H:%M:%S')


def get_instance(conf, name='__default'):
    with open(os.path.expanduser(conf), mode='r') as fh:
        data = yaml.load(fh)
    assert name in data, 'unknown instance'
    entry = data[name]
    if isinstance(entry, dict):
        return entry
    else:
        return data[entry]


def get_workflow_from_file(gi, workflow_file):
    import_workflow = [gi.workflows.import_workflow_from_local_path(file_local_path = workflow_file)]
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


def upload_datasets_from_folder(gi, experimentDir, history_name, history):
    if os.path.exists(experimentDir):
        expAcc = os.path.basename(experimentDir)
        files = os.listdir(experimentDir)
        history_id = history['id']

    # uploading each file from the experiment directory to a history id
    # and record appended files history
    datasets = []
    for file in files:
        print "Uploading %s ..." %(file)
        file_type = file.split(".")[-1]
        if file_type == 'mtx' or file_type == 'gz':
            file_type = 'auto'
        data = gi.tools.upload_file(path=os.path.join(experimentDir,file), history_id = history_id, file_name = file, file_type = file_type)
        datasets.append(data.items())
    return datasets


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


def make_data_map(experimentDir, datasets, show_workflow):
    datamap = {}
    files = os.listdir(experimentDir)
    for file in files:
        for idx, hist_dict in enumerate(datasets):
            if datasets[idx][0][1][0]['name'] == file:
                input_data_id = get_input_data_id(file, show_workflow)
                datamap[input_data_id] = { 'src':'hda', 'id': get_history_id(file, datasets[idx][0][1]) }
    if isinstance(datamap, dict):
        return(datamap)


def get_run_state(gi, results):
    results_hid = gi.histories.show_history(results['history_id'])
    state = results_hid['state']
    return state


def download_results(gi, results, experimentDir):
    results_hid = gi.histories.show_history(results['history_id'])
    ok_state_ids = results_hid['state_ids']['ok']
    for state_id in ok_state_ids:
        gi.datasets.download_dataset(state_id, file_path=experimentDir, use_default_filename=True)


def set_params(json_wf, param_data):
    params = {}
    for param_step_name in param_data:
        step_ids = (key for key, value in json_wf['steps'].iteritems() if value['label'] == str(param_step_name))
        for step_id in step_ids:
            params.update({step_id: param_data[param_step_name]})
    return params


def main():
    try:
        args = get_args()
        set_logging_level(args.debug)

        # Prepare environment
        logging.info('Prepare galaxy environment ...')
        ins = get_instance(args.conf, name=args.instance)
        gi = GalaxyInstance(ins['url'], key=ins['key'])

        # Create new history to run workflow
        logging.info('Create new history to run workflow ...')
        history = gi.histories.create_history(name=args.history)

        # upload dataset to history
        logging.info('Uploading dataset to history ...')
        datasets = upload_datasets_from_folder(gi, args.experimentDir, args.history, history)

        # get saved workflow defined in the galaxy instance
        logging.info('Workflow setup ...')
        json_wf = read_json_file(args.workflow)
        workflow = get_workflow_from_file(gi, workflow_file = args.workflow)
        workflow_id = get_workflow_id(wf = workflow)
        show_wf = gi.workflows.show_workflow(workflow_id)

        # create input datamap dictionary linking uploaded inputs files with workflow inputs
        logging.info('Datamap linking uploaded inputs and workflow inputs ...')
        datamap = make_data_map(args.experimentDir, datasets, show_wf)

        # set parameters
        logging.info('Set parameters ...')
        param_data = read_json_file(args.parameters)
        params = set_params(json_wf, param_data)

        logging.info('Running workflow ...')
        results = gi.workflows.invoke_workflow(workflow_id = workflow_id, inputs = datamap,
                                               params = params,
                                               history_name = (args.history + '_results'))

        binary_file = open(os.path.join(args.experimentDir, args.history + '_results.bin'), mode = 'wb')
        pickle.dump(results, binary_file)
        binary_file.close()

        # wait for a little while and check if the status is ok
        time.sleep(100)

        # get_run_state
        state = get_run_state(gi, results)

        # wait until the jobs are completed
        while state == 'queued':
            state = get_run_state(gi, results)
            if state == 'queued':
                time.sleep(10)
                continue
            elif state == 'ok':
                logging.info("jobs ok")
                break

        # Download results
        logging.info('Downloading results ...')
        download_results(gi, results, experimentDir = args.experimentDir)
        exit(0)
    except:
        exit(1)


if __name__ == '__main__':
    main()



