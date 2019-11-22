from setuptools import setup, find_packages
from glob import glob


setup(
    name="specter-desktop", 
    packages=find_packages('src'),
    package_dir={'': 'src'}
)