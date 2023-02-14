from babel.messages import frontend as babel
from glob import glob

from setuptools import find_namespace_packages, setup

from setuptools.command.install import install


class InstallWithBabelCompile(install):
    """from this stackoverflow question
    https://stackoverflow.com/questions/40051076/compile-translation-files-when-calling-setup-py-install
    """

    def run(self):
        from babel.messages.frontend import compile_catalog

        compiler = compile_catalog(self.distribution)
        option_dict = self.distribution.get_option_dict("compile_catalog")
        compiler.domain = [option_dict["domain"][1]]
        compiler.directory = option_dict["directory"][1]
        compiler.run()
        super().run()


with open("requirements.txt") as f:
    install_reqs = f.read().strip().split("\n")

# Filter out comments/hashes
reqs = []
for req in install_reqs:
    if req.startswith("#") or req.startswith("    --hash="):
        continue
    reqs.append(str(req).rstrip(" \\"))

setup(
    package_data={
        "": [
            "translations/*/LC_MESSAGES/messages.mo",
        ]
    },
    # take METADATA.in into account, include that stuff as well (static/templates)
    install_requires=reqs,
    cmdclass={
        "install": InstallWithBabelCompile,
        # The rest is convenience but not strictly necessary for the automation:
        "compile_catalog": babel.compile_catalog,
        "extract_messages": babel.extract_messages,
        "init_catalog": babel.init_catalog,
        "update_catalog": babel.update_catalog,
    },
)
