from setuptools import setup, find_packages

def readme():
    with open('README.md') as f:
        return f.read()


print(find_packages())

setup(
        name='galaxy-workflow-executor',
        version='0.1.1',
        description='Execute workflows on Galaxy through the CLI',
        long_description=readme(),
        packages=find_packages(),
        install_requires=['bioblend==0.12.0'],
        author='Suhaib Mohammed, Pablo Moreno',
        author_email='',
        scripts=['run_galaxy_workflow.py', 'generate_params_from_workflow.py'],
        license='MIT'
    )
