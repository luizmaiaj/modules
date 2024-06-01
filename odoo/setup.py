from setuptools import setup, find_packages

setup(
    name='odoo',
    version='0.1.8',
    packages=find_packages(),
    install_requires=[
        'dataclasses',
        'tomli'
    ],
    author='Luiz Maia',
    author_email='odoo@luiz.be',
    description='Odoo integration module.',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/luizmaiaj/odoo',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
)
