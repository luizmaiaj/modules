from setuptools import setup, find_packages

setup(
    name='nas',
    version='0.1.4',
    packages=find_packages(),
    install_requires=[
        'pysmb',
    ],
    author='Luiz Maia',
    author_email='nas@luiz.be',
    description='Tool functions to handle nas files.',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/luizmaiaj/nas',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS',
    ],
    python_requires='>=3.7',
)
