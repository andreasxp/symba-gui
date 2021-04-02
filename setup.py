"""Setup script for symba-gui package."""
from setuptools import setup, find_packages
from pathlib import Path

def setuptools_glob_workaround(package_name, glob):
    # https://stackoverflow.com/q/27664504/9118363
    package_path = Path(f'./{package_name}').resolve()
    return [str(path.relative_to(package_path)) for path in package_path.glob(glob)]

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

package_data = {
    "symba_gui": setuptools_glob_workaround("symba_gui", "data/**/*")
}

setup(
    name="symba-gui",
    version="0.1",
    description="Symba market simulator",
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points=entry_points,
    packages=find_packages(include=["symba_gui*"]),
    package_data=package_data,
)
