from setuptools import setup, find_packages

setup(
    name="build_influence",
    version="0.1.3",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "litellm",
        "mcp",
        "loguru",
        "pytest",
        "typer[all]",
        "pyyaml",
        "python-dotenv",
        "python-box",
        "tqdm",
        "rich",
    ],
    entry_points={
        "console_scripts": [
            "build-influence=build_influence.cli:app",
        ],
    },
)
