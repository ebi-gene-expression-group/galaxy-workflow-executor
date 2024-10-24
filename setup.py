from setuptools import find_packages, setup


def readme():
    with open('README.md') as f:
        return f.read()


print(find_packages())

setup(
        name='galaxy-workflow-executor',
        version='0.3.0',
        description='Execute workflows on Galaxy through the CLI',
        long_description=readme(),
        packages=find_packages(),
        install_requires=['bioblend==1.3.0', 'PyYAML'],
        author='Suhaib Mohammed, Pablo Moreno, Anil Thanki',
        long_description_content_type='text/markdown',
        author_email='',
        scripts=['run_galaxy_workflow.py', 'generate_params_from_workflow.py'],
        license='MIT'
    )
