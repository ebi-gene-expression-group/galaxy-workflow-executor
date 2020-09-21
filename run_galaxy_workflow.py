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
import os.path
from sys import exit
from bioblend.galaxy import GalaxyInstance
from bioblend import ConnectionError

from wfexecutor import *
# Exit status:
# 3 - history deletion problem
#from wfexecutor import download_results, set_params, load_input_files, validate_labels, validate_input_labels, \
#    validate_file_exists, validate_dataset_id_exists, completion_state, process_allowed_errors, produce_versions_file


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
                            required=True,
                            help='Workflow to run')
    arg_parser.add_argument('-P', '--parameters',
                            default=None,
                            required=False,
                            help='parameters file, by default json')
    arg_parser.add_argument('--parameters-yaml',
                            default=False,
                            action='store_true',
                            help='read parameters file as yaml instead of json')
    arg_parser.add_argument('--debug',
                            action='store_true',
                            default=False,
                            help='Print debug information')
    arg_parser.add_argument('-a', '--allowed-errors',
                            required=False,
                            default=None,
                            help="Yaml file with allowed steps that can have errors."
                            )
    arg_parser.add_argument('-s', '--state-file',
                            help="Path to read and save the execution state file.",
                            default="exec_state.pickle"
                            )
    arg_parser.add_argument('-k', '--keep-histories',
                            action='store_true',
                            default=False,
                            help="Keeps histories created, they will be purged if not.")
    arg_parser.add_argument('-w', '--keep-workflow',
                            action='store_true',
                            default=False,
                            help="Keeps workflow created, it will be purged if not.")
    arg_parser.add_argument('--publish', action='store_true',
                            default=False, help="Keep result history and make it public/accesible.")
    arg_parser.add_argument('--accessible', action='store_true',
                            default=False, help="Keep result history and make it accessible via link only.")
    args = arg_parser.parse_args()
    return args


def set_logging_level(debug=False):
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format='%(asctime)s - %(message)s',
        datefmt='%d-%m-%y %H:%M:%S')


def main():
    try:
        args = get_args()
        set_logging_level(args.debug)

        # Load workflows, inputs and parameters
        wf_from_json = read_json_file(args.workflow)
        if args.parameters:
            param_data = read_yaml_file(args.parameters) if args.parameters_yaml else read_json_file(args.parameters)
        else:
            param_data = dict()
        inputs_data = read_yaml_file(args.yaml_inputs_path)
        allowed_error_states = {'tools': {}, 'datasets': set()}
        if args.allowed_errors is not None:
            allowed_error_states = \
                process_allowed_errors(read_yaml_file(args.allowed_errors), wf_from_json)

        # Move any simple parameters from parameters to inputs
        params_to_move = []
        for pk, pv in param_data.items():
            if not isinstance(pv, Mapping):
                # this means that it is an atomic value and not a dictionary
                # so this is a simple input
                params_to_move.append(pk)

        for pk in params_to_move:
            inputs_data[pk] = param_data[pk]
            del param_data[pk]

        # Validate data before talking to Galaxy
        validate_labels(wf_from_json, param_data)
        num_inputs = validate_input_labels(wf_json=wf_from_json, inputs=inputs_data)
        if num_inputs > 0:
            validate_file_exists(inputs_data)

        # Prepare environment and do any post connection validations.
        logging.info('Prepare galaxy environment...')
        ins = get_instance(args.conf, name=args.galaxy_instance)
        gi = GalaxyInstance(ins['url'], key=ins['key'])
        validate_dataset_id_exists(gi, inputs_data)

        state = ExecutionState.start(path=args.state_file)

        # Create new history to run workflow
        if state.input_history is None:
            logging.info('Create new history to run workflow ...')
            if num_inputs > 0:
                history = gi.histories.create_history(name=args.history)
                state.input_history = history
                state.save_state()
        else:
            logging.info('Using history available in state file')
            history = state.input_history

        # get saved workflow defined in the galaxy instance
        logging.info('Workflow setup ...')
        if state.wf_from_file is None:
            workflow = get_workflow_from_file(gi, workflow_file=args.workflow)
            state.wf_from_file = workflow
            state.save_state()
        else:
            workflow = state.wf_from_file
        workflow_id = get_workflow_id(wf=workflow)
        show_wf = gi.workflows.show_workflow(workflow_id)

        # upload dataset to history
        if state.datamap is None:
            logging.info('Uploading dataset to history ...')
            if num_inputs > 0:
                datamap = load_input_files(gi, inputs=inputs_data,
                                           workflow=show_wf, history=history)
            else:
                datamap = {}
            state.datamap = datamap
            # set parameters
            logging.info('Set parameters ...')
            params = set_params(wf_from_json, param_data)
            state.params = params
            state.save_state()
        else:
            datamap = state.datamap
            params = state.params

        if state.results is None:
            try:
                logging.info('Running workflow {}...'.format(show_wf['name']))
                results = gi.workflows.invoke_workflow(workflow_id=workflow_id,
                                                       inputs=datamap,
                                                       params=params,
                                                       history_name=(args.history + '_results'))
                state.results = results
                state.save_state()
            except Exception as ce:
                logging.error("Failure when invoking invoke workflows: {}".format(str(ce)))
                raise ce
        else:
            logging.info("Invocation result present in state, resuming that invocation")
            results = state.results

        # Produce tool versions file
        produce_versions_file(gi=gi, workflow_from_json=wf_from_json,
                              path="{}/software_versions_galaxy.txt".format(args.output_dir))

        # wait for a little while and check if the status is ok
        logging.info("Waiting for results to be available...")
        logging.info("...in the mean time, you can check {}/histories/view?id={} for progress."
                     "You need to login with the user that owns the API Key.".
                     format(gi.base_url, results['history_id']))
        time.sleep(100)

        # get_run_state
        results_hid = gi.histories.show_history(results['history_id'])
        state = results_hid['state']

        # wait until workflow invocation is fully scheduled, cancelled of failed
        while True:
            invocation = gi.workflows.show_invocation(workflow_id=results['workflow_id'], invocation_id=results['id'])
            if invocation['state'] in ['scheduled', 'cancelled', 'failed']:
                # These are the terminal states of the invocation process. Scheduled means that all jobs needed for the
                # workflow have been scheduled, not that the workflow is finished. However, there is no point in
                # checking completion through history elements if this hasn't happened yet.
                logging.info("Workflow invocation has entered a terminal state: {}".format(invocation['state']))
                logging.info("Proceeding to check individual jobs state to determine completion or failure...")
                break
            time.sleep(10)

        # wait until the jobs are completed, once workflow scheduling is done.
        logging.debug("Got state: {}".format(state))
        while True:
            logging.debug("Got state: {}".format(state))
            error_state, finalized_state = completion_state(gi, results_hid, allowed_error_states)
            # TODO could a resubmission be caught here in the 'error' state?
            if error_state:
                logging.error("Execution failed, see {}/histories/view?id={} for input details."
                              "You might require login with a particular user.".
                              format(gi.base_url, results_hid['id']))
                exit(1)
            elif finalized_state:
                logging.info("Workflow finished successfully OK or with allowed errors.")
                break
            # TODO downloads could be triggered here to gain time.
            time.sleep(10)
            results_hid = gi.histories.show_history(results['history_id'])
            state = results_hid['state']

        # Download results
        logging.info('Downloading results ...')
        download_results(gi, history_id=results['history_id'],
                         output_dir=args.output_dir, allowed_error_states=allowed_error_states,
                         use_names=True)
        logging.info('Results available.')
        logging.info('Deleting state file {}'.format(args.state_file))
        os.unlink(args.state_file)

        if args.publish:
            gi.histories.update_history(results['history_id'], published=True)
            logging.info("Results history made public...")
        elif args.accessible:
            gi.histories.update_history(results['history_id'], importable=True)
            logging.info("Results history made accesible...")

        if not args.keep_histories:
            logging.info('Deleting histories...')
            try:
                if not args.publish and not args.accessible:
                    logging.info("Not deleting results history as marked as shared or published...")
                    gi.histories.delete_history(results['history_id'], purge=True)
                if num_inputs > 0:
                    gi.histories.delete_history(history['id'], purge=True)
            except ConnectionError:
                logging.error('Connection was interrupted while trying to delete histories, '
                              'although this probably succeded at the server, you should check that they have been deleted.')
                hist_to_delete_path = os.path.join(args.output_dir, 'histories_to_check.txt')
                logging.info('Adding collection identifiers to be checked to {}'.format(hist_to_delete_path))
                with open(hist_to_delete_path, mode="w") as f:
                    for hist in results['history_id'], history['id']:
                        f.write(str(hist)+"\n")
                logging.info("Exiting with error code 3 now to signal the connection error on history deletion.")
                logging.info("Data should have been downloaded fine, "
                             "and there is no reason not to proceed with any posterior analysis")
                exit(3)
            logging.info('Histories purged...')

        if not args.keep_workflow:
            logging.info('Deleting workflow...')
            try:
                gi.workflows.delete_workflow(workflow_id=workflow_id)
                logging.info('Workflow deleted.')
            except ConnectionError:
                logging.error('Connection was interrupted while trying to delete the workflow, '
                              'although this probably succeeded at the server... ignoring.')

        exit(0)
    except Exception as e:
        logging.error("Failed due to {}".format(str(e)))
        raise e


if __name__ == '__main__':
    main()



