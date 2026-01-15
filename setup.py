from setuptools import setup

setup(
    name="mineru-cli",
    version="0.1.4",
    description="MinerU Cloud OCR CLI Tool",
    author="Your Name",
    py_modules=["mineru_cli"],
    install_requires=[
        "requests",
    ],
    entry_points={
        "console_scripts": [
            "mineru=mineru_cli:main",
        ],
    },
    python_requires=">=3.6",
)
