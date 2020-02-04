from setuptools import setup, find_packages
from glob import glob

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="specter-desktop",
    version="v0.0.11",
    author="Stepan Snigirev",
    author_email="snigirev.stepan@gmail.com",
    description="A GUI for Bitcoin Core optimised to work with airgapped hardware wallets",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cryptoadvance/specter-desktop",
    packages=find_packages('src'),
    package_dir={'': 'src'},
    # take METADATA.in into account, include that stuff as well (static/templates)
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Framework :: Flask",
    ],
    python_requires='>=3.6',
)
