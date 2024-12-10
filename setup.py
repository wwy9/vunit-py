import setuptools

with open("README.md", "r", encoding="utf8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="vunit-py",  # Replace with your own username
    version="0.0.2",
    author="Weiyi Wu",
    author_email="w1w2y3@gmail.com",
    description="vunit-py generate testbench written in python for VUnit",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/wwy9/vunit-py",
    packages=["vunit_py"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Intended Audience :: Developers",
        "Natural Language :: Chinese (Simplified)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Testing",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
        "Typing :: Typed",
    ],
    python_requires='>=3.6',
    install_requires=["vunit_hdl>=4.7.0"],
)
