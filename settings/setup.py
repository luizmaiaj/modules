from setuptools import setup, find_packages

setup(
    name='settings',
    version='0.2.3',
    packages=find_packages(),
    install_requires=[
        'dataclasses',
        'tomli'
    ],
    author='Luiz Maia',
    author_email='settings@luiz.be',
    description='Settings management module.',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/luizmaiaj/settings',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.11',
)
