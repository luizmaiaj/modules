from setuptools import setup, find_packages

setup(
    name='ado2odoo',
    version='0.1.3',
    packages=find_packages(),
    install_requires=[
        'requests',  # Assuming ado2odoo.py might use requests
    ],
    author='Luiz Maia',
    author_email='ado2odoo@luiz.be',
    description='Integration module for ADO to Odoo.',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/luizmaiaj/ado2odoo',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
)
