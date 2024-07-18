from setuptools import setup, find_packages

setup(
    name='search',
    version='0.1.11',
    packages=find_packages(),
    install_requires=[
        'pillow',
        'requests',
        'google-api-python-client',
        'duckduckgo-search',
        'python-dotenv',
        'beautifulsoup4',
        'lxml',
        'html5lib'
    ],
    author='Luiz Maia',
    author_email='search@luiz.be',
    description='Seach module.',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/luizmaiaj/search',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
)
