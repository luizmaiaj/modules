from setuptools import setup, find_packages

setup(
    name='gitea2odoo',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'requests',  # Assuming gitea2odoo.py might use requests
    ],
    author='Luiz Maia',
    author_email='gitea2odoo@luiz.be',
    description='Integration module for Gitea to Odoo.',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/luizmaiaj/gitea2odoo',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
)
