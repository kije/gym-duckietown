import sys

from setuptools import find_packages, setup


def get_version(filename):
    import ast

    version = None
    with open(filename) as f:
        for line in f:
            if line.startswith("__version__"):
                version = ast.parse(line).body[0].value.s
                break
        else:
            raise ValueError("No version found in %r." % filename)
    if version is None:
        raise ValueError(filename)
    return version


version = get_version(filename="src/gym_duckietown/__init__.py")

line = "daffy"

install_requires = [
    "gymnasium>=1.1.0,<1.2.0",  # 1.2.0+ requires Python 3.10+
    "numpy>=1.21.0,<1.24.0,<2.0",  # duckietown_world requires NumPy 1.x
    "scipy>=1.5.0,<1.11.0",  # 1.11.0+ requires Python 3.9+
    "pyglet>=2.0.0",
    "pyzmq>=16.0.0",
    "opencv-python>=3.4",
    "PyYAML>=3.11",
    f"duckietown-world-{line}",
    "PyGeometry-z6",
    "carnivalmirror==0.6.2",
    "zuper-commons-z6>=6.2.3",
    "typing_extensions",
    "Pillow",
]


setup(
    name=f"duckietown-gym-{line}",
    package_dir={"": "src"},
    packages=find_packages("src"),
    zip_safe=False,
    version=version,
    python_requires=">=3.8",
    keywords="duckietown, environment, agent, rl, openaigym, openai-gym, gym, gymnasium",
    include_package_data=True,
    install_requires=install_requires,
    entry_points={
        "console_scripts": [
            "dt-check-gpu=gym_duckietown.check_hw:main",
        ],
    },
)
