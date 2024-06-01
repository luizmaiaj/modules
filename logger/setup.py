from setuptools import setup, find_packages

setup(
    name='logger',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'streamlit',
        'dataclasses'
    ],
    author='Luiz Maia',
    author_email='logger@luiz.be',
    description='Logging module for Streamlit interface.',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/luizmaiaj/logger',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
)
