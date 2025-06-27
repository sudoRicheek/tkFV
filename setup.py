from setuptools import setup, find_packages

setup(
    name="tkFV",
    version="1.0.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    entry_points={
        'console_scripts': [
            'tkFV=tkFV.tkFV:main',
        ],
    },
    install_requires=[],
    author="Your Name",
    description="A Tkinter-based file viewer application",
    python_requires='>=3.10',
)
