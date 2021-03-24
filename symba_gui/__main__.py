import sys
import os
import traceback
import json
import shlex
import shutil
from subprocess import Popen
from pathlib import Path
from copy import deepcopy
from zipfile import ZipFile

from PySide2.QtCore import Qt, QStandardPaths, QDir, QSize
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QMenu, QWidget, QLineEdit, QVBoxLayout, QDockWidget, QFormLayout, QGridLayout,
    QFileDialog, QDialog, QCheckBox, QMessageBox, QListWidget, QDialogButtonBox, QFrame, QTextEdit, QComboBox,
    QHBoxLayout, QPushButton, QSpinBox, QDoubleSpinBox, QStyleFactory, QTabWidget, QStyle
)
from PySide2.QtSvg import QSvgWidget
from pyqtgraph import PlotWidget, PlotItem, BarGraphItem

import symba_gui as package
from .cli import parse_args
from .dpi import inches_to_pixels as px
from .widgets import PathEdit
from .simulation import Simulation


class PrefsExePicker(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences: Symba Executables")

        self.executables = None
        self.user_choice = None
        self.builtin = None

        self.wpath_list = QListWidget()
        self.wpath_list.setSortingEnabled(True)
        self.wpath_list.setAlternatingRowColors(True)
        self.wpath_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.wpath_list.currentTextChanged.connect(self.currentTextChangedEvent)
        self.wpath_list.customContextMenuRequested.connect(self.actionShowContextMenu)

        self.wis_default = QCheckBox("Make this executable default for new simulations")
        self.wis_default.setEnabled(False)
        self.wis_default.stateChanged.connect(self.checkboxStateChangedEvent)

        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.wbutton_ok = button_box.button(QDialogButtonBox.Save)
        self.wbutton_cancel = button_box.button(QDialogButtonBox.Cancel)

        self.wbutton_ok.clicked.connect(self.accept)
        self.wbutton_cancel.clicked.connect(self.reject)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)

        ly = QVBoxLayout()
        self.setLayout(ly)

        ly.addWidget(self.wpath_list)
        ly.addWidget(self.wis_default)
        ly.addWidget(line)
        ly.addWidget(button_box)
    
    def actionShowContextMenu(self, pos):
        global_pos = self.wpath_list.mapToGlobal(pos)
        item = self.wpath_list.itemAt(pos)

        if item is None:
            menu = QMenu()
            action_add_path = menu.addAction("Add Path...")

            def getPath():
                path = QFileDialog.getOpenFileName(
                    self, "Choose an executable for running the simulation", QDir.homePath(), "Executables (*.exe)"
                )[0]
                self.addPath(path)

            action_add_path.triggered.connect(getPath)

            menu.exec_(global_pos)
        elif item.text() == self.builtin:
            pass
        else:
            menu = QMenu()
            action_add_path = menu.addAction("Delete")
            action_add_path.triggered.connect(lambda: self.removePath(item.text()))

            menu.exec_(global_pos)

    def currentTextChangedEvent(self, text):
        self.wis_default.setChecked(text == self.user_choice)
        self.wis_default.setDisabled(text == self.builtin)

    def checkboxStateChangedEvent(self, checked):
        if checked == (self.user_choice == self.wpath_list.currentItem().text()):
            # Everything as it should be
            return

        if checked:
            self.user_choice = self.wpath_list.currentItem().text()
        else:
            self.user_choice = self.builtin

    def setData(self, executables, user_choice, builtin):
        """Set current data into the dialog."""
        self.executables = [str(path) for path in executables]
        self.user_choice = str(user_choice)
        self.builtin = str(builtin)

        self.original_executables = self.executables
        self.original_user_choice = self.user_choice

        self.wpath_list.clear()
        for path in self.executables:
            self.wpath_list.addItem(path)

    def addPath(self, path):
        if path not in self.executables:
            # No such path yet
            self.executables.append(path)
            self.wpath_list.addItem(path)
        
        item = self.wpath_list.findItems(path, Qt.MatchExactly)[0]
        self.wpath_list.setCurrentItem(item)
    
    def removePath(self, path):
        items = self.wpath_list.findItems(path, Qt.MatchExactly)
        if len(items) == 0:
            return

        item = self.wpath_list.findItems(path, Qt.MatchExactly)[0]
        self.wpath_list.takeItem(self.wpath_list.row(item))
        self.executables.remove(item.text())
        
        if self.user_choice == path:
            self.user_choice = self.builtin

    def data(self):
        return [Path(s) for s in self.executables], Path(self.user_choice)

    def closeEvent(self, event):
        if self.executables != self.original_executables or self.user_choice != self.original_user_choice:
            msg = QMessageBox(self)
            msg.setWindowTitle("Preferences: Symba Executables")
            msg.setText("Save changes to the executable list?")
            msg.setIcon(QMessageBox.Question)
            msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            msg.setDefaultButton(QMessageBox.Cancel)
            ret = msg.exec_()

            if ret == QMessageBox.Save:
                self.accept()
                event.accept()
            elif ret == QMessageBox.Discard:
                self.reject()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Exception catching -------------------------------------------------------------------------------------------
        self.__excepthook__ = sys.excepthook
        sys.excepthook = self.excepthook
        
        # Settings -----------------------------------------------------------------------------------------------------
        self.app_data_dir = Path(QStandardPaths.standardLocations(QStandardPaths.AppDataLocation)[0])
        """Directory of user-specific application data."""
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        
        if (self.app_data_dir / "config.json").exists():
            # Load config file
            with open(self.app_data_dir / "config.json", "r", encoding="utf-8") as f:
                config = json.load(f)

            self.save_dir = Path(config["save_dir"])
            self.builtin_executable = Path(config["executables"]["built-in"])
            self.executable = Path(config["executables"]["user-choice"])
            self.executables = [Path(s) for s in config["executables"]["paths"]]
        else:
            # If config file does not exist, create from defaults and write it
            self.save_dir = Path(QStandardPaths.standardLocations(QStandardPaths.DocumentsLocation)[0])
            self.builtin_executable = package.dir / "bin" / "symba.exe"
            self.executable = self.builtin_executable
            self.executables = [self.builtin_executable]

            with open(self.app_data_dir / "config.json", "w", encoding="utf-8") as f:
                json.dump(self.config(), f, ensure_ascii=False, indent=4)

        # Simulation data ----------------------------------------------------------------------------------------------
        self.opened_file = None  # Which file is this instance associated with. Changes with New or Open actions.
        self.simulated = None  # Whether this simulation has been completed or not (initialized later).
        self.saved_simulated = None
        self.saved_model_params = None

        self.output_dir = self.app_data_dir / "instances" / str(os.getpid())
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Clean data from previous launches
        for file in self.output_dir.rglob("*"):
            file.unlink()

        # Contents -----------------------------------------------------------------------------------------------------
        w = QWidget()
        ly = QVBoxLayout()
        w.setLayout(ly)
        self.setCentralWidget(w)

        self.wdock_config = QDockWidget("Simulation Properties")
        self.wdock_config.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.wdock_config.visibilityChanged.connect(lambda visible: self.action_view_config.setChecked(visible))
        self.addDockWidget(Qt.LeftDockWidgetArea, self.wdock_config)

        self.wconfig = QWidget()
        self.wdock_config.setWidget(self.wconfig)
        lyconfig = QVBoxLayout()
        lyconfig.setSpacing(px(0.2))
        self.wconfig.setLayout(lyconfig)
        
        wconfigopts = QWidget()
        wconfigopts.setContentsMargins(0, 0, 0, 0)
        lyconfigopts = QFormLayout()
        lyconfigopts.setContentsMargins(0, 0, 0, 0)
        wconfigopts.setLayout(lyconfigopts)
        lyconfig.addWidget(wconfigopts)

        self.wsimulate_button = QPushButton(" Simulate")
        self.wsimulate_button.setIcon(QIcon(str(package.dir / "data/play.svg")))
        min_icon_size = QSize(
            self.wsimulate_button.sizeHint().height() * 0.5,
            self.wsimulate_button.sizeHint().height() * 0.5
        )
        self.wsimulate_button.setIconSize(min_icon_size)
        self.wsimulate_button.setFixedWidth(px(1.561))
        self.wsimulate_button.clicked.connect(self.actionSimulate)
        lyconfig.addWidget(self.wsimulate_button)
        lyconfig.setAlignment(self.wsimulate_button, Qt.AlignHCenter)
        lyconfig.addStretch()

        # Simulation options -------------------------------------------------------------------------------------------
        self.wn_agents = QSpinBox()
        self.wn_agents.setRange(10, 10000)
        lyconfigopts.addRow("Number of agents (I):", self.wn_agents)

        self.wn_stocks = QSpinBox()
        self.wn_stocks.setRange(1, 100)
        lyconfigopts.addRow("Number of stocks (J):", self.wn_stocks)

        self.wn_steps = QSpinBox()
        self.wn_steps.setRange(281, 10000)
        lyconfigopts.addRow("Number of time steps (T):", self.wn_steps)

        self.wn_rounds = QSpinBox()
        self.wn_rounds.setRange(1, 10000)
        lyconfigopts.addRow("Number of rounds (S):", self.wn_rounds)

        self.wrate = QDoubleSpinBox()
        self.wrate.setRange(0, 2)
        self.wrate.setSingleStep(0.01)
        lyconfigopts.addRow("Rate:", self.wrate)

        self.wplot = QCheckBox()
        lyconfigopts.addRow("Build plots:", self.wplot)

        self.wtype_neb = QComboBox()
        self.wtype_neb.addItems([
            "Classic", "Algorithmic", "Human", "LossAversion", "Positivity", "Negativity", "DelayDiscounting", "Fear",
            "Greed", "LearningRate"
        ])
        lyconfigopts.addRow("NEB type:", self.wtype_neb)

        self.whp_gesture = QDoubleSpinBox()
        self.whp_gesture.setRange(1, 10)
        self.wrate.setSingleStep(0.01)
        lyconfigopts.addRow("HP gesture:", self.whp_gesture)

        self.wliquidation_floor = QSpinBox()
        self.wliquidation_floor.setRange(0, 100)
        lyconfigopts.addRow("Liquidation floor:", self.wliquidation_floor)

        self.wleader_type = QComboBox()
        self.wleader_type.addItems(["Worst", "Best", "Static", "Noise", "NoCluster"])
        lyconfigopts.addRow("Leader type:", self.wleader_type)

        self.wcluster_limit = QSpinBox()
        self.wcluster_limit.setRange(0, 100)
        lyconfigopts.addRow("Cluster limit:", self.wcluster_limit)

        self.wadditional_args = QLineEdit()
        lyconfigopts.addRow("Additional arguments:", self.wadditional_args)

        # Plot area ----------------------------------------------------------------------------------------------------
        self.wplot_area = QTabWidget()

        wplot1 = PlotWidget()
        y1 = [5, 5, 7, 10, 3, 8, 9, 1, 6, 2]
        x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        bargraph = BarGraphItem(x=x, height=y1, width=0.6)
        wplot1.addItem(bargraph)

        self.wplot_area.addTab(wplot1, "test")
        self.wplot_area.addTab(QWidget(), "test2")

        self.wsim_placeholder = QWidget()
        self.wsim_placeholder.setMinimumSize(px(8.695), px(6.522))
        wsim_placeholder_svg = QSvgWidget(str(package.dir / "data/sim_placeholder.svg"))
        wsim_placeholder_svg.setFixedSize(wsim_placeholder_svg.renderer().defaultSize())

        lysim_placeholder = QGridLayout()
        lysim_placeholder.setRowStretch(0, 10)
        lysim_placeholder.setRowStretch(2, 15)
        lysim_placeholder.setColumnStretch(0, 1)
        lysim_placeholder.setColumnStretch(2, 1)
        lysim_placeholder.addWidget(wsim_placeholder_svg, 1, 1)
        self.wsim_placeholder.setLayout(lysim_placeholder)
        self.setCentralWidget(self.wplot_area)

        self.wdock_exepicker = QDockWidget("Executable Selection")
        self.wdock_exepicker.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.wdock_exepicker.visibilityChanged.connect(lambda visible: self.action_view_exepicker.setChecked(visible))
        self.wdock_exepicker.hide()
        self.addDockWidget(Qt.LeftDockWidgetArea, self.wdock_exepicker)
        
        self.wexepicker = QWidget()
        lyexepicker = QHBoxLayout()
        self.wexepicker.setLayout(lyexepicker)
        self.wdock_exepicker.setWidget(self.wexepicker)

        self.exepicker_combobox = QComboBox()
        for path in self.executables:
            self.exepicker_combobox.addItem(str(path))
        self.exepicker_combobox.setCurrentText(str(self.executable))

        exepicker_button = QPushButton("Configure...")
        exepicker_button.clicked.connect(self.actionShowPrefsExePicker)
        
        lyexepicker.addWidget(self.exepicker_combobox)
        lyexepicker.addWidget(exepicker_button)

        # Menu bar -----------------------------------------------------------------------------------------------------
        menu_bar = self.menuBar()

        menu_file = menu_bar.addMenu("File")
        
        action_new = menu_file.addAction("New Simulation")
        action_new.triggered.connect(self.actionNew)

        action_new_window = menu_file.addAction("New Window")
        action_new_window.triggered.connect(self.actionNewWindow)

        menu_file.addSeparator()
        menu_file.addAction("Open...")
        menu_file.addSeparator()
        action_save = menu_file.addAction("Save")
        action_save.triggered.connect(self.actionSave)
        action_save_as = menu_file.addAction("Save As...")
        action_save_as.triggered.connect(self.actionSaveAs)
        menu_file.addSeparator()
        menu_preferences = menu_file.addMenu("Preferences")
        action_prefs_exepicker = menu_preferences.addAction("Symba Executables")
        action_prefs_exepicker.triggered.connect(self.actionShowPrefsExePicker)
        menu_file.addSeparator()
        action_exit = menu_file.addAction("Exit")
        action_exit.triggered.connect(self.actionExit)

        menu_view = menu_bar.addMenu("View")
        self.action_view_config = menu_view.addAction("Simulation Properties")
        self.action_view_config.setCheckable(True)
        self.action_view_config.setChecked(True)
        self.action_view_config.triggered.connect(lambda checked: self.wdock_config.setVisible(checked))
        self.action_view_exepicker = menu_view.addAction("Executable Selection")
        self.action_view_exepicker.setCheckable(True)
        self.action_view_exepicker.setChecked(False)
        self.action_view_exepicker.triggered.connect(lambda checked: self.wdock_exepicker.setVisible(checked))

        # --------------------------------------------------------------------------------------------------------------
        self.loadNewFile()

    def modelChanged(self):
        """Return True if the model configuration/simulation is different from when the file was first opened."""
        return self.saved_simulated != self.simulated or self.saved_model_params != self.modelParams()

    def modelParams(self):
        """Generate a dict of simulation parameters. Dict keys are long CLI parameters without --.
        The dict does not include application-defined parameters, such as output-dir.
        """
        args = {
            "n-agents": self.wn_agents.value(),
            "n-stocks": self.wn_stocks.value(),
            "n-steps": self.wn_steps.value(),
            "n-rounds": self.wn_rounds.value(),
            "rate": self.wrate.value(),
            "plot": self.wplot.isChecked(),
            "type-neb": self.wtype_neb.currentText(),
            "hp-gesture": self.whp_gesture.value(),
            "liquidation-floor": self.wliquidation_floor.value(),
            "leader-type": self.wleader_type.currentText(),
            "cluster-limit": self.wcluster_limit.value(),

            # Special value for storing extra parameters
            "__extra": shlex.split(self.wadditional_args.text())
        }

        return args

    def cliArgs(self):
        """Generate a list of CLI arguments for launching current configuration in symba executable."""
        # Add model paramterers
        args_dict = self.modelParams()
        args = []

        extra = args_dict["__extra"]
        args_dict.pop("__extra")

        for key, value in args_dict.items():
            args.append("--" + key)
            args.append(str(value))
        
        args += extra

        # Add hidden parameters
        output_dir = ["--output-dir", str(self.output_dir)]
        args += output_dir
        return args

    def config(self):
        """Get all persistent configuration options as a dict."""
        config = {
            "executables": {
                "paths": [str(path) for path in self.executables],
                "user-choice": str(self.executable),
                "built-in": str(self.builtin_executable)
            },
            "save_dir": str(self.save_dir)
        }

        return config

    def loadFile(self, path):
        """Load file from zip, without prompting user for changes."""
        pass
    
    def loadNewFile(self):
        self.opened_file = None
        self.simulated = False
        self.saved_simulated = self.simulated  # For comparison for "save changes" dialog

        self.wn_agents.setValue(500)
        self.wn_stocks.setValue(1)
        self.wn_steps.setValue(3875)
        self.wn_rounds.setValue(1)
        self.wrate.setValue(0.01)
        self.wplot.setChecked(False)
        self.wtype_neb.setCurrentText("Classic")
        self.whp_gesture.setValue(1)
        self.wliquidation_floor.setValue(50)
        self.wleader_type.setCurrentText("NoCluster")
        self.wcluster_limit.setValue(1)
        self.wadditional_args.setText("")

        self.saved_model_params = self.modelParams()  # For comparison for "save changes" dialog

    def saveFile(self, path):
        """Save current model to zip."""
        if not self.simulated:
            # If not simulated, just write the model parameters.
            with open(self.output_dir / "ModelParameters.json", "w", encoding="utf-8") as f:
                json.dump(self.modelParams(), f, ensure_ascii=False, indent=4)
        
        with ZipFile(path, "w") as zip:
            for file in self.output_dir.rglob("*"):
                zip.write(file, file.relative_to(self.output_dir))
        
        self.opened_file = path
        # Update saved_ values
        self.saved_simulated = self.simulated
        self.saved_model_params = self.modelParams()

    # Actions ==========================================================================================================
    def promptSaveChanges(self) -> bool:
        """Prompt the user to save changes to current project.
        Display a message box asking the user if they want to save changes. If user selects Save, execute actionSave.
        Returns True if the user decided to discard changes or saved the file, and False if the user cancelled operation
        either during prompt or during save.
        """
        prompt = QMessageBox()
        prompt.setWindowTitle("Save changes to this file?")
        prompt.setIcon(QMessageBox.Warning)

        if self.opened_file is None:
            prompt.setText(f"Save changes to this model before closing?")
        else:
            prompt.setText(f"Save changes to \"{self.opened_file.name}\" before closing?")

        prompt.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        prompt.setDefaultButton(QMessageBox.Save)
        
        answer = prompt.exec_()
        if answer == QMessageBox.Cancel:
            return False
        if answer == QMessageBox.Save:
            return self.actionSave()
        return True

    def actionNew(self):
        if self.modelChanged():
            if not self.promptSaveChanges():
                # Model changed and user cancelled during prompt
                return
        
        self.loadNewFile()

    def actionNewWindow(self):
        """Start a new experiment. Opens a new window.
        
        This process launches a new simulation window by creating a detached process. The way the process is created
        depends on sys.argv[0] (what is the origin of this process).
        """
        pos_x = self.pos().x() + 40
        pos_y = self.pos().y() + 40
        cli_args = ["--window-pos", f"{pos_x},{pos_y}"]

        if sys.argv[0].endswith("__main__.py"):
            # Application launched with python
            Popen(
                [sys.executable, "-m", Path(sys.argv[0]).parent.name] + cli_args,
                cwd=Path(sys.argv[0]).parent.parent
            )
        else:
            # Assume the application was launched using an executable
            Popen([sys.argv[0]] + cli_args)

    def actionSave(self) -> bool:
        if self.opened_file:
            self.saveFile(self.opened_file)
            return True  # Success
        
        return self.actionSaveAs()

    def actionSaveAs(self) -> bool:
        if self.opened_file:
            save_dir = self.opened_file
        else:
            save_dir = self.save_dir / "Untitled.symba"

        dialog = QFileDialog(
            parent=self, caption="Save As", directory=str(save_dir), filter="Simulation Files (*.symba)"
        )
        dialog.setFileMode(dialog.AnyFile)
        dialog.setAcceptMode(dialog.AcceptSave)
        dialog.setDefaultSuffix(".symba")

        ok = dialog.exec_()
        self.save_dir = Path(dialog.directory().absolutePath())

        if not ok:
            return False  # User cancelled
        
        path = Path(dialog.selectedFiles()[0])
        self.saveFile(path)
        return True

    def actionExit(self):
        # All actions are handled in closeEvent()
        self.close()
    
    def actionSimulate(self):
        """Start the simulation."""
        args = self.cliArgs()
        print([str(self.executable)] + args)

        self.simulation = Simulation([str(self.executable)] + args)
        self.simulation.stepChanged.connect(lambda round, step: print(f"{round}: {step}"))
        self.simulation.completed.connect(self.onSimulationCompleted)
        self.simulation.start()
    
    # Properties =======================================================================================================
    def actionShowPrefsExePicker(self):
        """Show preferences dialog for the execuatable picker."""
        dialog = PrefsExePicker(self)
        dialog.setData(self.executables, self.executable, self.builtin_executable)

        def finishedEvent(result):
            if result:
                self.executables, self.executable = dialog.data()

                current_path = Path(self.exepicker_combobox.currentText())
                self.exepicker_combobox.clear()
                for path in self.executables:
                    self.exepicker_combobox.addItem(str(path))

                if current_path in self.executables:
                    self.exepicker_combobox.setCurrentText(str(current_path))
                else:
                    self.exepicker_combobox.setCurrentText(str(self.executable))

        dialog.finished.connect(finishedEvent)

        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    # Events ===========================================================================================================
    def closeEvent(self, event):
        if self.modelChanged():
            if not self.promptSaveChanges():
                # Model changed and user cancelled during prompt
                event.ignore()
                return

        # Remove output directory for this instance
        shutil.rmtree(self.output_dir)

        with open(self.app_data_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(self.config(), f, ensure_ascii=False, indent=4)

        event.accept()

    def onSimulationCompleted(self, result):
        if result != 0:
            raise RuntimeError("The simulation completed with errors")

    # Exception handling ===============================================================================================
    def excepthook(self, etype, value, tb):
        message = QMessageBox(self)
        message.setWindowTitle("Critical Error")
        message.setText(
            "An unknown critical error occured. It is recommended to save your work and restart Symba Designer.\n\n"
            "Please inform the developer, describing what you were doing before the error, and attach the text below."
        )
        message.setIcon(message.Icon.Critical)

        exception_field = QTextEdit()
        exception_field.setText("".join(traceback.format_exception(etype, value, tb)))
        exception_field.setReadOnly(True)
        message.layout().addWidget(exception_field, 1, 0, 1, -1)
        message.exec_()

        self.__excepthook__(etype, value, tb)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("symba_gui")
    app.setApplicationDisplayName("Symba Designer")
    app.setStyle(QStyleFactory.create("fusion"))
    args = parse_args()

    main_window = MainWindow()
    if args.window_pos is not None:
        main_window.move(*args.window_pos)

    main_window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
