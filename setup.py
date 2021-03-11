"""Setup script for symba-gui package."""
from setuptools import setup, find_packages

install_requires = [
    "pyside2",
    "pyqtgraph"
]

extras_require = {
    "freeze":  [
        "pyinstaller",
    ]
}

entry_points = {
    "gui_scripts": ["symba-gui = symba_gui.__main__:main"],
    "console_scripts": ["symba-gui-d = symba_gui.__main__:main"]
}

setup(
    name="symba-gui",
    version="0.1",
    description="Symba market simulator",
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points=entry_points,
    packages=find_packages(),
    #package_data=package_data,
)
