from setuptools import setup, find_packages

setup(
    name='ocr',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'pyobjc-framework-Cocoa',
        'pyobjc-framework-Quartz',
        'pyobjc-framework-Vision'
    ],
    author='Luiz Maia',
    author_email='ocr@luiz.be',
    description='OCR functions using Vision framework.',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/luizmaiaj/ocr',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS',
    ],
    python_requires='>=3.6',
)
