#!/usr/bin/env python3

import io
import os
import sys
from shutil import rmtree
import subprocess  # For better command execution handling
from setuptools import setup, Command

# Package meta-data.
NAME = 'requests-html'
DESCRIPTION = 'HTML Parsing for Humans.'
URL = 'https://github.com/psf/requests-html'
EMAIL = 'me@kennethreitz.org'
AUTHOR = 'Kenneth Reitz'
VERSION = '0.10.0'

# Required packages.
REQUIRED = [
    'requests', 'pyquery', 'fake-useragent', 'parse', 'beautifulsoup4', 'w3lib', 'pyppeteer>=0.0.14'
]

# Absolute path to current directory.
here = os.path.abspath(os.path.dirname(__file__))

# Import the README and use it as the long-description, with a file check.
readme_path = os.path.join(here, 'README.rst')
if os.path.exists(readme_path):
    with io.open(readme_path, encoding='utf-8') as f:
        long_description = '\n' + f.read()
else:
    long_description = DESCRIPTION  # Fallback if README is missing.

class UploadCommand(Command):
    """Support for setup.py upload. Build and publish the package to PyPI."""
    description = 'Build and publish the package.'
    user_options = []

    @staticmethod
    def status(s):
        """Prints status messages in bold for better visibility."""
        print('\033[1m{0}\033[0m'.format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            self.status('Removing previous builds…')
            rmtree(os.path.join(here, 'dist'))
        except FileNotFoundError:
            self.status('No previous builds to remove.')
        except Exception as e:
            print(f"Error while removing previous builds: {e}")
            sys.exit(1)

        self.status('Building Source and Wheel (universal) distribution…')
        result = subprocess.run([sys.executable, 'setup.py', 'sdist', 'bdist_wheel', '--universal'])
        if result.returncode != 0:
            print('Error during building the distribution')
            sys.exit(1)

        self.status('Uploading the package to PyPi via Twine…')
        result = subprocess.run(['twine', 'upload', 'dist/*'])
        if result.returncode != 0:
            print('Error during upload')
            sys.exit(1)

        self.status('Publishing git tags…')
        result = subprocess.run(['git', 'tag', f'v{VERSION}'])
        if result.returncode == 0:
            subprocess.run(['git', 'push', '--tags'])
        else:
            print('Error creating git tag')
            sys.exit(1)

        sys.exit()

# Setup function.
setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type='text/x-rst',  # Specify the format of long description.
    author=AUTHOR,
    author_email=EMAIL,
    url=URL,
    python_requires='>=3.6.0',
    py_modules=['requests_html'],
    install_requires=REQUIRED,
    include_package_data=True,
    license='MIT',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy'
    ],
    cmdclass={
        'upload': UploadCommand,
    },
)
