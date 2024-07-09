from setuptools import setup, find_packages

setup(
    name='gitea',
    version='0.1.2',
    packages=find_packages(),
    install_requires=[
        'requests',  # Assuming gitea.py might use requests to interact with Gitea API
    ],
    author='Luiz Maia',
    author_email='gitea@luiz.be',
    description='Gitea integration module.',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/luizmaiaj/gitea',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
)
