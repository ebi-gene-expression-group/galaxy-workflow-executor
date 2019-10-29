#!/usr/bin/env python

"""generate_params_from_workflow

This script generate json parameter file from galaxy workflow using config_credentials.yml file provided.
provisioned locally in a directory. This scripts connects to galaxy instance and grabs parameters 
using bioblend galaxy instance.

running syntax

python generate_params_from_workflow.py \
        -C galaxy_credentials.yml.sample \
        -G 'ebi_cluster' \
        -o $PWD \
        -N 'scanpy_param_test' \
        -W scanpy_clustering_workflow.json 

File galaxy_credentials.yml.sample must contain url and key.
"""

import json
import argparse
import os.path
from bioblend.galaxy import GalaxyInstance
import yaml
import logging
from sys import exit


def get_args():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-C', '--conf',
                            required=True,
                            help='A yaml file describing the galaxy credentials')
    arg_parser.add_argument('-G', '--galaxy-instance',
                            default='ebi_cluster',
                            help='Galaxy server instance name')
    arg_parser.add_argument('-o', '--output-dir',
                            default="./",
                            help='Path to output directory')
    arg_parser.add_argument('-N', '--name-parameter',
                            default='scanpy_params',
                            required=True,
                            help='Name of the parameter file to create')
    arg_parser.add_argument('-W', '--workflow',
                            default='scanpy_clustering_workflow',
                            required=True,
                            help='Workflow to run')
    arg_parser.add_argument('--debug',
                            action='store_true',
                            default=False,
                            help='Print debug information')

    args = arg_parser.parse_args()
    return args


def get_instance(conf, name='__default'):
    with open(os.path.expanduser(conf), mode='r') as fh:
        data = yaml.load(fh)
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

def get_workflow_from_file(gi, workflow_file):
    import_workflow = [gi.workflows.import_workflow_from_local_path(file_local_path = workflow_file)]
    return import_workflow

def get_workflow_id(wf):
    for wf_dic in wf:
        wf_id = wf_dic['id']
    return wf_id

def set_logging_level(debug=False):
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format= '%(asctime)s - %(message)s',
        datefmt='%d-%m-%y %H:%M:%S')


def main():
    try:
        args = get_args()
        set_logging_level(args.debug)

        # Prepare environment
        logging.info('Prepare galaxy environment ...')
        ins = get_instance(args.conf, name=args.galaxy_instance)
        gi = GalaxyInstance(ins['url'], key=ins['key'])

        # get saved workflow defined in the galaxy instance
        logging.info('Workflow setup ...')
        json_wf = read_json_file(args.workflow)
        workflow = get_workflow_from_file(gi, workflow_file=args.workflow)
        workflow_id = get_workflow_id(wf=workflow)
        show_wf = gi.workflows.show_workflow(workflow_id)

        param = {}
        for key, value in json_wf['steps'].iteritems():
            if str(value['label']) != 'None':
                step_id=key
                step_name=value['label']
                param.update({step_name: show_wf['steps'][step_id]['tool_inputs']})

        with open((os.path.join(args.output_dir,args.name_parameter) + ".json"), 'w') as f:
            json.dump(param, f, indent=4, sort_keys=True)
            print('parameter output file:',(os.path.join(args.output_dir,args.name_parameter) + ".json"))

    except:
        exit(1)

if __name__ == '__main__':
        main()
