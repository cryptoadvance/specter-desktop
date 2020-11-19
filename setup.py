from glob import glob

from setuptools import find_namespace_packages, setup

with open("requirements.txt") as f:
    install_reqs = f.read().strip().split("\n")


# Filter out comments/hashes
reqs = []
for req in install_reqs:
    if req.startswith("#") or req.startswith("    --hash="):
        continue
    reqs.append(str(req).rstrip(" \\"))


with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="cryptoadvance.specter",
    version="vx.y.z-get-replaced-by-release-script",
    author="Stepan Snigirev, Kim Neunert",
    author_email="snigirev.stepan@gmail.com, kim.neunert@gmail.com",
    description="A GUI for Bitcoin Core optimised to work with airgapped hardware wallets",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cryptoadvance/specter-desktop",
    packages=find_namespace_packages("src", include=["cryptoadvance.*"]),
    package_dir={"": "src"},
    # take METADATA.in into account, include that stuff as well (static/templates)
    include_package_data=True,
    install_requires=reqs,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Framework :: Flask",
    ],
    python_requires=">=3.6,<3.9",
)
