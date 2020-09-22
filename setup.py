from setuptools import setup, find_packages


def readme():
    with open('README.md') as f:
        return f.read()


print(find_packages())

setup(
        name='galaxy-workflow-executor',
        version='0.2.2',
        description='Execute workflows on Galaxy through the CLI',
        long_description=readme(),
        packages=find_packages(),
        install_requires=['bioblend==0.13.0'],
        author='Suhaib Mohammed, Pablo Moreno',
        long_description_content_type='text/markdown',
        author_email='',
        scripts=['run_galaxy_workflow.py', 'generate_params_from_workflow.py'],
        license='MIT'
    )
