# pip install virtualenv

set +e
docker stop galaxy-test-instance
docker rm galaxy-test-instance
set -e
api_key=ahsdashdi3d3oijd23odj23
helper_user_email="helper@help.co"
docker run -d -p 8080:80 -p 8021:21 -p 8022:22 \
    --name galaxy-test-instance \
    -e "GALAXY_CONFIG_MASTER_API_KEY=$api_key" \
    -e "GALAXY_CONFIG_ADMIN_USERS=$helper_user_email,admin@galaxy.org" \
    -e "NONUSE=nodejs,proftp,reports" \
    -e "GALAXY_CONFIG_ALLOW_PATH_PASTE=true" \
    bgruening/galaxy-stable:19.09
rm -rf venv-test
# virtualenv venv-test
python3 -m venv venv-test
source venv-test/bin/activate
pip install wheel
pip install . ephemeris galaxy-parsec
galaxy-wait -g http://localhost:8080/
admin_id=$(parsec -g test -f test/parsec_creds.yaml users get_users | jq '.[] | select(.username=="admin") | .id' | sed s/\"//g)
api_key_admin=$(parsec -g test -f test/parsec_creds.yaml users create_user_apikey $admin_id)

# create a user with admin privs, as the default admin user fails to uploads files to the data library
user_id=$(parsec -g test -f test/parsec_creds.yaml users create_local_user helper_user $helper_user_email 'helper.pass_56%' | jq '.id' | sed s/\"//g)
user_api_key=$(parsec -g test -f test/parsec_creds.yaml users create_user_apikey $user_id)

sed "s/<ADMIN_USER_API_KEY>/$user_api_key/" test/test_galaxy_credentials.yaml.template > test/creds.yaml

# create a library with parsec
library_id=$(parsec -g test -f test/parsec_creds.yaml libraries create_library test_library | jq '.id' | sed s/\"//g)
echo "Library ID: $library_id"
# upload file_with_2_cols.txt to library to use as second input.
command="parsec -g test -f test/creds.yaml libraries upload_file_from_local_path --file_type tabular $library_id test/file_with_2_cols.txt"
echo "Command: $command"
ls -l test/file_with_2_cols.txt
# parsec -g test -f test/creds.yaml libraries upload_file_from_local_path --file_type tabular $library_id test/file_with_2_cols.txt
file_library_id=$(parsec -g test -f test/creds.yaml libraries upload_file_from_local_path --file_type tabular $library_id test/file_with_2_cols.txt | jq '.[] | select(.name=="file_with_2_cols.txt") | .id' | sed s/\"//g) 
# exit 1
echo "File library ID: $file_library_id"

sed "s/<INPUT_TO_MERGE_LIBRARY_ID>/$file_library_id/" test/wf_inputs.yaml.template > test/wf_inputs.yaml

mkdir -p test_out
run_galaxy_workflow.py -C test/creds.yaml \
    -G test -o test_out/ -H 'test history' -W test/wf.json \
    -i test/wf_inputs.yaml -P test/wf_parameters.yaml \
    --parameters-yaml

# Runs a test with data upload to datalib 
run_galaxy_workflow.py -C test/creds.yaml \
    -G test -l test -H 'lib test history' -W test/wf.json \
    -i test/wf_inputs.yaml -P test/wf_parameters.yaml \
    --parameters-yaml
