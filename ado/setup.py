from setuptools import setup, find_packages

setup(
    name='ado',
    version='0.1.5',
    packages=find_packages(),
    install_requires=[
        'requests',
        'Pillow',
        'progress'
    ],
    author='Luiz Maia',
    author_email='ado@luiz.be',
    description='Tool functions to access Azure DevOps.',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/luizmaiaj/ado',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS',
    ],
    python_requires='>=3.7',
)
