from setuptools import setup, find_packages

setup(
    name="build_influence",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        # Dependencies will be read from requirements.txt
        # Add other metadata here if needed
    ],
    entry_points={
        "console_scripts": [
            "build-influence=build_influence.cli:app",
        ],
    },
)
