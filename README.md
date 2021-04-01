# Symba Designer
Symba Designer is an application for designing simulations of financial markets. It is a graphical user interface for the [CLI application](https://github.com/andreasxp/symba-releases) called Symba.

## Installing Symba Designer
Symba Designer is available on any Windows, MacOS or Linux machine with an x64 architecture.  
Prerequisites: [Python 3](https://www.python.org/).

To install the application on your machine, download and run the installer via Python's included package manager, pip:
```
pip3 install symba-gui@https://github.com/andreasxp/symba-gui/archive/master.zip
```

Then launch the application by running the command:
```
symba-gui
```

### Installing Symba Designer (for developers)
Prerequisites: [Python 3](https://www.python.org/), [git](https://git-scm.com/).

To install symba in dev mode, git-clone it to your machine, and run the editable pip install process:
```
git clone https://github.com/andreasxp/symba-gui/archive/master.zip
pip install --editable symba-gui
```
For the experimental executable freezing support, install symba with the `freeze` attribute:
```
pip install --editable symba-gui[freeze]
```

Besides starting Symba as `symba-gui`, you can also execute `symba-gui-d` to start it in debug mode. This will print all exceptions to the command line.
Alternatively, you can launch Symba as a python module using `python -m symba_gui`. This is equivalent to `symba-gui-d`.
