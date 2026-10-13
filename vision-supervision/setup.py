from setuptools import setup, find_packages

setup(
    name="vision-supervision",
    version="0.4.0",
    description="Librería nativa de supervisión por computadora, desde principios fundamentales "
                "(shim: el motor canónico vive en supervisionvidaeo.vision)",
    author="Yael Méndez",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.24.0",
        "opencv-python-headless>=4.8.0",
    ],
    python_requires=">=3.10",
)
