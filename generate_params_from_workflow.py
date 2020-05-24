#!/usr/bin/env python

"""generate_params_from_workflow

This script generate json parameter file from galaxy workflow using galaxy_credentials.yml.sample file provided in repo.
provisioned locally in a directory. This scripts connects to galaxy instance and grabs parameters 
from galaxy workflow object and deletes workflow in galaxy instance.

running syntax

python generate_params_from_workflow.py \
        -C galaxy_credentials.yml.sample \
        -G 'ebi_cluster' \
        -o $PWD \
        -W scanpy_clustering_workflow.json 

File galaxy_credentials.yml.sample must contain url and key.

Output parameter file will be appended with workflow_filename as workflow_filename_parameters.json in output dir.
"""

import argparse
import os.path
from bioblend.galaxy import GalaxyInstance

from wfexecutor import *


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


def set_logging_level(debug=False):
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format= '%(asctime)s - %(message)s',
        datefmt='%d-%m-%y %H:%M:%S')


def main():
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

        param_file=(os.path.join(args.output_dir,os.path.basename(args.workflow).split('.')[0]) + "_parameters.json")
        with open(param_file, 'w') as f:
            yaml.dump(param, f, indent=4, sort_keys=True)
            print("parameter output file : " + param_file)

        # delete workflow from galaxy instance
        logging.info("Deleting workflow...")
        gi.workflows.delete_workflow(workflow_id=workflow_id)



if __name__ == '__main__':
        main()
