# pip install virtualenv
set -e
rm -rf venv-test
virtualenv venv-test
source venv-test/bin/activate
pip install . ephemeris parsec

api_key=ahsdashdi3d3oijd23odj23
set +e
docker stop galaxy-test-instance
docker rm galaxy-test-instance
set -e
docker run -d -p 8080:80 -p 8021:21 -p 8022:22 \
    --name galaxy-test-instance \
    -e "GALAXY_CONFIG_MASTER_API_KEY=$api_key" \
    -e "NONUSE=nodejs,proftp,reports" \
    bgruening/galaxy-stable:19.09
galaxy-wait -g http://localhost:8080/
admin_id=$(parsec -g local_cont users get_users | jq '.[] | select(.username=="admin") | .id' | sed s/\"//g)
api_key_admin=$(parsec -g local_cont users create_user_apikey $admin_id)

sed "s/<ADMIN_USER_API_KEY>/$api_key_admin/" test/test_galaxy_credentials.yaml.template > test/creds.yaml

mkdir -p test_out
run_galaxy_workflow.py -C test/creds.yaml \
    -G test -o test_out/ -H 'test history' -W test/wf.json \
    -i test/wf_inputs.yaml -P test/wf_parameters.yaml \
    --parameters-yaml