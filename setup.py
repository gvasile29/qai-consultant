"""Build hook only; all metadata lives in pyproject.toml.

qai_consultant/cli.py is the app-side Rich terminal UI (imports the Pinecone/LLM
tiers). It lives in the package for the repo's own use but must never ship in the
keyless MCP wheel, and setuptools' package finder cannot exclude a single module.
"""
from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

_APP_SIDE_MODULES = {("qai_consultant", "cli")}


class build_py(_build_py):
    def find_package_modules(self, package, package_dir):
        return [m for m in super().find_package_modules(package, package_dir)
                if (m[0], m[1]) not in _APP_SIDE_MODULES]


setup(cmdclass={"build_py": build_py})
