import sys
import os
import traceback
import json
import shlex
import shutil
from subprocess import Popen
from pathlib import Path
from zipfile import ZipFile

from PySide2.QtCore import Qt, QStandardPaths, QSize
from PySide2.QtGui import QIcon, QFontDatabase
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLineEdit, QVBoxLayout, QDockWidget, QFormLayout, QGridLayout,
    QFileDialog, QCheckBox, QMessageBox, QDialogButtonBox, QTextEdit, QComboBox, QSizePolicy, QStackedWidget,
    QHBoxLayout, QPushButton, QSpinBox, QDoubleSpinBox, QStyleFactory, QTabWidget, QProgressBar
)
from PySide2.QtSvg import QSvgWidget
from pyqtgraph import PlotWidget, PlotItem, BarGraphItem

import symba_gui as package
from .cli import parse_args
from .dpi import inches_to_pixels as px
from .simulation import Simulation
from .prefs_exepicker import PrefsExePicker
from .chart import ChartEditor, Chart


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Exception catching
        self.__excepthook__ = sys.excepthook
        sys.excepthook = self.excepthook

        # Loading fonts ================================================================================================
        for path in (package.dir / "data" / "fonts").glob("*"):
            QFontDatabase.addApplicationFont(str(path))
        
        # Application properties =======================================================================================
        self.app_data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
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
            self.save_dir = Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation))
            self.builtin_executable = package.dir / "bin" / "symba.exe"
            self.executable = self.builtin_executable
            self.executables = [self.builtin_executable]

            with open(self.app_data_dir / "config.json", "w", encoding="utf-8") as f:
                json.dump(self.config(), f, ensure_ascii=False, indent=4)

        # Simulation properties (initialized in self.loadFile or self.loadNewFile)
        self.opened_file = None  # Which file is this instance associated with. Changes with New or Open actions.
        self.simulation = None
        self.saved_model_params = None
        self._unsaved_changes = False

        temp_dir = Path(QStandardPaths.writableLocation(QStandardPaths.TempLocation))
        self.output_dir = temp_dir / "symba_gui" / "instances" / str(os.getpid())
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_chart_dir = self.output_dir / "Charts"  # Will be created when a chart is added

        # Clean data from previous launches
        shutil.rmtree(self.output_dir)
        self.output_dir.mkdir()

        # Dock widgets =================================================================================================
        w = QWidget()
        ly = QVBoxLayout()
        w.setLayout(ly)
        self.setCentralWidget(w)

        # Simulation control -------------------------------------------------------------------------------------------
        self.wdock_control = QDockWidget("Simulation")
        self.wdock_control.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.wdock_control.visibilityChanged.connect(lambda visible: self.action_view_control.setChecked(visible))
        self.addDockWidget(Qt.LeftDockWidgetArea, self.wdock_control)
        
        self.wcontrol = QWidget()
        self.wdock_control.setWidget(self.wcontrol)
        lycontrol = QVBoxLayout()
        self.wcontrol.setLayout(lycontrol)

        wcontainer = QWidget()
        wcontainer.setContentsMargins(0, 0, 0, 0)
        lycontainer = QHBoxLayout()
        lycontainer.setContentsMargins(0, 0, 0, 0)
        wcontainer.setLayout(lycontainer)

        self.wsim_button = QPushButton(" Simulate")
        self.wsim_button.setIcon(QIcon(str(package.dir / "data/play.svg")))
        self.wsim_button.setIconSize(QSize(px(0.125), px(0.125)))
        self.wsim_button.clicked.connect(self.actionStartSimulation)
        lycontainer.addWidget(self.wsim_button)

        self.wsim_progess_bar = QProgressBar()
        lycontainer.addWidget(self.wsim_progess_bar)
        lycontrol.addWidget(wcontainer)
        lycontrol.addStretch()

        # Simulation Properties ----------------------------------------------------------------------------------------
        self.wdock_config = QDockWidget("Simulation Properties")
        self.wdock_config.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.wdock_config.visibilityChanged.connect(lambda visible: self.action_view_config.setChecked(visible))
        self.addDockWidget(Qt.LeftDockWidgetArea, self.wdock_config)

        self.wconfig = QWidget()
        self.wdock_config.setWidget(self.wconfig)
        lyconfig = QFormLayout()
        self.wconfig.setLayout(lyconfig)

        # Model parameters
        self.wn_agents = QSpinBox()
        self.wn_agents.setRange(10, 10000)
        lyconfig.addRow("Number of agents (I):", self.wn_agents)

        self.wn_stocks = QSpinBox()
        self.wn_stocks.setRange(1, 100)
        lyconfig.addRow("Number of stocks (J):", self.wn_stocks)

        self.wn_steps = QSpinBox()
        self.wn_steps.setRange(281, 10000)
        lyconfig.addRow("Number of time steps (T):", self.wn_steps)

        self.wn_rounds = QSpinBox()
        self.wn_rounds.setRange(1, 10000)
        lyconfig.addRow("Number of rounds (S):", self.wn_rounds)

        self.wrate = QDoubleSpinBox()
        self.wrate.setRange(0, 2)
        self.wrate.setSingleStep(0.01)
        lyconfig.addRow("Rate:", self.wrate)

        self.wplot = QCheckBox()
        lyconfig.addRow("Build plots:", self.wplot)

        self.wtype_neb = QComboBox()
        self.wtype_neb.addItems([
            "Classic", "Algorithmic", "Human", "LossAversion", "Positivity", "Negativity", "DelayDiscounting", "Fear",
            "Greed", "LearningRate"
        ])
        lyconfig.addRow("NEB type:", self.wtype_neb)

        self.whp_gesture = QDoubleSpinBox()
        self.whp_gesture.setRange(1, 10)
        self.wrate.setSingleStep(0.01)
        lyconfig.addRow("HP gesture:", self.whp_gesture)

        self.wliquidation_floor = QSpinBox()
        self.wliquidation_floor.setRange(0, 100)
        lyconfig.addRow("Liquidation floor:", self.wliquidation_floor)

        self.wleader_type = QComboBox()
        self.wleader_type.addItems(["Worst", "Best", "Static", "Noise", "NoCluster"])
        lyconfig.addRow("Leader type:", self.wleader_type)

        self.wcluster_limit = QSpinBox()
        self.wcluster_limit.setRange(0, 100)
        lyconfig.addRow("Cluster limit:", self.wcluster_limit)

        self.wadditional_args = QLineEdit()
        lyconfig.addRow("Additional arguments:", self.wadditional_args)

        # Executable picker --------------------------------------------------------------------------------------------
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

        # Central area =================================================================================================
        self.wcentral_widget = QStackedWidget()
        self.setCentralWidget(self.wcentral_widget)

        # No simulation placeholder ------------------------------------------------------------------------------------
        self.wno_sim_placeholder = QWidget()
        self.wno_sim_placeholder.setMinimumSize(px(8.695), px(6.522))
        wno_sim_placeholder_svg = QSvgWidget(str(package.dir / "data/no_sim_placeholder.svg"))
        wno_sim_placeholder_svg.setFixedSize(wno_sim_placeholder_svg.renderer().defaultSize())

        lyno_sim_placeholder = QGridLayout()
        lyno_sim_placeholder.setRowStretch(0, 10)
        lyno_sim_placeholder.setRowStretch(2, 15)
        lyno_sim_placeholder.setColumnStretch(0, 1)
        lyno_sim_placeholder.setColumnStretch(2, 1)
        lyno_sim_placeholder.addWidget(wno_sim_placeholder_svg, 1, 1)
        self.wno_sim_placeholder.setLayout(lyno_sim_placeholder)

        self.wcentral_widget.addWidget(self.wno_sim_placeholder)

        # No chart placeholder -----------------------------------------------------------------------------------------
        self.wno_chart_placeholder = QWidget()
        self.wno_chart_placeholder.setMinimumSize(px(8.695), px(6.522))
        lyno_chart_placeholder = QGridLayout()
        self.wno_chart_placeholder.setLayout(lyno_chart_placeholder)
        
        lyno_chart_placeholder.setSpacing(px(0.2))
        lyno_chart_placeholder.setRowStretch(0, 10)
        lyno_chart_placeholder.setRowStretch(3, 15)
        lyno_chart_placeholder.setColumnStretch(0, 1)
        lyno_chart_placeholder.setColumnStretch(2, 1)

        wno_chart_placeholder_svg = QSvgWidget(str(package.dir / "data/no_chart_placeholder.svg"))
        wno_chart_placeholder_svg.setFixedSize(wno_chart_placeholder_svg.renderer().defaultSize())
        lyno_chart_placeholder.addWidget(wno_chart_placeholder_svg, 1, 1)

        wno_chart_placeholder_add_chart_button = QPushButton(" Add Chart")
        wno_chart_placeholder_add_chart_button.setIcon(QIcon(str(package.dir / "data/plus.svg")))
        wno_chart_placeholder_add_chart_button.setIconSize(QSize(px(0.125), px(0.125)))
        wno_chart_placeholder_add_chart_button.clicked.connect(self.actionAddChart)
        lyno_chart_placeholder.addWidget(wno_chart_placeholder_add_chart_button, 2, 1, Qt.AlignHCenter)

        self.wcentral_widget.addWidget(self.wno_chart_placeholder)

        # Chart area ---------------------------------------------------------------------------------------------------
        self.wcharts = QTabWidget()
        self.wcharts.setMovable(True)

        wcontainer = QWidget()
        wcontainer.setContentsMargins(0, 0, px(0.01), px(0.01))
        lycontainer = QHBoxLayout()
        lycontainer.setContentsMargins(0, 0, 0, 0)
        lycontainer.setSpacing(px(0.01))
        wcontainer.setLayout(lycontainer)

        self.wadd_chart_button = QPushButton()
        self.wadd_chart_button.setIcon(QIcon(str(package.dir / "data/plus.svg")))
        self.wadd_chart_button.setFixedSize(px(0.21), px(0.21))
        self.wadd_chart_button.setIconSize(QSize(px(0.125), px(0.125)))
        self.wadd_chart_button.clicked.connect(self.actionAddChart)

        self.wedit_chart_button = QPushButton()
        self.wedit_chart_button.setIcon(QIcon(str(package.dir / "data/play.svg")))
        self.wedit_chart_button.setFixedSize(px(0.21), px(0.21))
        self.wedit_chart_button.setIconSize(QSize(px(0.125), px(0.125)))
        self.wedit_chart_button.clicked.connect(self.actionEditCurrentChart)

        self.wremove_chart_button = QPushButton()
        self.wremove_chart_button.setIcon(QIcon(str(package.dir / "data/stop.svg")))
        self.wremove_chart_button.setFixedSize(px(0.21), px(0.21))
        self.wremove_chart_button.setIconSize(QSize(px(0.125), px(0.125)))
        self.wremove_chart_button.clicked.connect(self.actionRemoveCurrentChart)

        lycontainer.addWidget(self.wadd_chart_button)
        lycontainer.addWidget(self.wedit_chart_button)
        lycontainer.addWidget(self.wremove_chart_button)

        self.wcharts.setCornerWidget(wcontainer)
        self.wcentral_widget.addWidget(self.wcharts)

        # Menu bar =====================================================================================================
        menu_bar = self.menuBar()

        menu_file = menu_bar.addMenu("File")
        
        action_new = menu_file.addAction("New Simulation")
        action_new.triggered.connect(self.actionNew)

        action_new_window = menu_file.addAction("New Window")
        action_new_window.triggered.connect(self.actionNewWindow)

        menu_file.addSeparator()
        action_open = menu_file.addAction("Open...")
        action_open.triggered.connect(self.actionOpen)
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
        self.action_view_control = menu_view.addAction("Simulation")
        self.action_view_control.setCheckable(True)
        self.action_view_control.setChecked(True)
        self.action_view_control.triggered.connect(lambda checked: self.wdock_control.setVisible(checked))
        self.action_view_config = menu_view.addAction("Simulation Properties")
        self.action_view_config.setCheckable(True)
        self.action_view_config.setChecked(True)
        self.action_view_config.triggered.connect(lambda checked: self.wdock_config.setVisible(checked))
        self.action_view_exepicker = menu_view.addAction("Executable Selection")
        self.action_view_exepicker.setCheckable(True)
        self.action_view_exepicker.setChecked(False)
        self.action_view_exepicker.triggered.connect(lambda checked: self.wdock_exepicker.setVisible(checked))

        # ==============================================================================================================
        self.loadNewFile()

    @property
    def unsaved_changes(self) -> bool:
        """True if the user has unsaved changes.
        Depends on whether unsaved_changes was saved manually and whetner model parameters were edited.
        """
        return self._unsaved_changes or self.saved_model_params != self.modelParams()

    @unsaved_changes.setter
    def unsaved_changes(self, value: bool):
        self._unsaved_changes = value

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
        self.opened_file = path
        self.simulation = Simulation()
        self.simulation.completed.connect(self.onSimulationFinished)

        # Clean directory
        shutil.rmtree(self.output_dir)
        self.output_dir.mkdir()

        if self.opened_file is None:
            # Create new file
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

            self.wcentral_widget.setCurrentWidget(self.wno_sim_placeholder)
        else:
            with ZipFile(path, "r") as zip:
                zip.extractall(self.output_dir)
            
            with open(self.output_dir / "ModelParameters.json", "r", encoding="utf-8") as f:
                params = json.load(f)
            
            self.wn_agents.setValue(params["n-agents"])
            self.wn_stocks.setValue(params["n-stocks"])
            self.wn_steps.setValue(params["n-steps"])
            self.wn_rounds.setValue(params["n-rounds"])
            self.wrate.setValue(params["rate"])
            self.wplot.setChecked(params["plot"])
            self.wtype_neb.setCurrentText(params["type-neb"])
            self.whp_gesture.setValue(params["hp-gesture"])
            self.wliquidation_floor.setValue(params["liquidation-floor"])
            self.wleader_type.setCurrentText(params["leader-type"])
            self.wcluster_limit.setValue(params["cluster-limit"])
            self.wadditional_args.setText("")

            if len(list(self.output_dir.iterdir())) > 1:
                # Assume that the file was simulated
                self.wcharts.clear()
                
                if self.output_chart_dir.exists():
                    for chart_path in self.output_chart_dir.iterdir():
                        self.wcharts.addTab(Chart(self.output_dir, chart_path), chart_path.stem)
                    
                if self.wcharts.count() > 0:
                    self.wcentral_widget.setCurrentWidget(self.wcharts)
                else:
                    self.wcentral_widget.setCurrentWidget(self.wno_chart_placeholder)
            else:
                self.wcentral_widget.setCurrentWidget(self.wno_sim_placeholder)

        self.saved_model_params = self.modelParams()  # For comparison for "save changes" dialog
        self.unsaved_changes = False
    
    def loadNewFile(self):
        self.loadFile(None)

    def saveFile(self, path):
        """Save current model to zip."""
        if not (self.output_dir / "ModelParameters.json").exists():
            # If model parameters were not written by the simulation, write our own
            with open(self.output_dir / "ModelParameters.json", "w", encoding="utf-8") as f:
                json.dump(self.modelParams(), f, ensure_ascii=False, indent=4)
        
        # Remove __pycache__ from the Charts folder
        pycache = self.output_dir / "Charts" / "__pycache__"
        if pycache.exists():
            shutil.rmtree(pycache)

        # Write to zip
        with ZipFile(path, "w") as zip:
            for file in self.output_dir.rglob("*"):
                zip.write(file, file.relative_to(self.output_dir))
        
        self.opened_file = path
        # Update saved_ values
        self.saved_model_params = self.modelParams()
        self.unsaved_changes = False

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
            prompt.setText("Save changes to this model before closing?")
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
    
    def promptStopSimulation(self) -> bool:
        """Prompt the user to stop the simulation.
        If the user declines, return False. If the user accepts, return True.
        """
        prompt = QMessageBox()
        prompt.setWindowTitle("Stop simulation?")
        prompt.setIcon(QMessageBox.Warning)
        prompt.setText("Stop running this simulation?")
        prompt.setInformativeText("If the simulation is stopped, no results will be saved.")

        prompt.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        prompt.setDefaultButton(QMessageBox.Cancel)
        
        answer = prompt.exec_()
        if answer == QMessageBox.Cancel:
            return False
        if answer == QMessageBox.Ok:
            return True
        return True

    def actionNew(self):
        if self.unsaved_changes:
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

    def actionOpen(self):
        if self.unsaved_changes:
            if not self.promptSaveChanges():
                # User cancelled during prompt
                return
        
        dialog = QFileDialog(
            parent=self, caption="Open", directory=str(self.save_dir), filter="Simulation Files (*.symba)"
        )
        dialog.setFileMode(dialog.ExistingFile)
        dialog.setAcceptMode(dialog.AcceptOpen)

        ok = dialog.exec_()
        self.save_dir = Path(dialog.directory().absolutePath())

        if not ok:
            return False  # User cancelled
        
        path = Path(dialog.selectedFiles()[0])
        self.loadFile(path)

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
    
    def actionStartSimulation(self):
        """Start the simulation."""
        self.unsaved_changes = True

        # Clean directory
        shutil.rmtree(self.output_dir)
        self.output_dir.mkdir()

        # Remove existing charts and switch to the placeholder
        self.wcharts.clear()
        self.wcentral_widget.setCurrentWidget(self.wno_sim_placeholder)

        # Configure progress bar
        self.wsim_progess_bar.setRange(0, 0)

        n_rounds = self.wn_rounds.value()
        n_steps = self.wn_steps.value()
        def updateProgressBar(round, step):
            self.wsim_progess_bar.setRange(0, n_rounds * n_steps)
            self.wsim_progess_bar.setValue(round * n_steps + step)
        self.simulation.stepChanged.connect(updateProgressBar)

        # Change start button to stop
        self.wsim_button.setIcon(QIcon(str(package.dir / "data/stop.svg")))
        self.wsim_button.setText(" Stop")
        self.wsim_button.clicked.disconnect(self.actionStartSimulation)
        self.wsim_button.clicked.connect(self.actionStopSimulation)

        args = [str(self.executable)] + self.cliArgs()
        self.simulation.start(args)
    
    def actionStopSimulation(self):
        if not self.promptStopSimulation():
            return
        
        self.simulation.terminate()
        self.wsim_button.setEnabled(False)  # Disable the button until the simulation is stopped
        self.wsim_progess_bar.setRange(0, 0)
    
    def actionAddChart(self):
        dialog = ChartEditor(self)

        def done(result):
            if not result:
                return  # User cancelled

            self.output_chart_dir.mkdir(parents=True, exist_ok=True)

            title = dialog.title
            code = dialog.code
            path = self.output_chart_dir / (title + ".py")

            with open(path, "w", encoding="utf-8") as f:
                f.write(code)

            self.unsaved_changes = True
            self.wcharts.addTab(Chart(self.output_dir, path), title)
            self.wcharts.setCurrentIndex(self.wcharts.count() - 1)
            self.wcentral_widget.setCurrentWidget(self.wcharts)

        dialog.finished.connect(done)

        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def actionEditCurrentChart(self):
        dialog = self.wcharts.currentWidget().editor()

        # Data on the tab is updated automatically, but we need some other processing also
        def done():
            self.unsaved_changes = True
            self.wcharts.setCurrentWidget(self.wcharts.currentWidget())

        dialog.finished.connect(done)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
    
    def actionRemoveCurrentChart(self):
        self.unsaved_changes = True
        self.wcharts.currentWidget().path.unlink()
        self.wcharts.removeTab(self.wcharts.currentIndex())

        if self.wcharts.count() == 0:
            self.wcentral_widget.setCurrentWidget(self.wno_chart_placeholder)

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
        if self.simulation.running:
            if not self.promptStopSimulation():
                event.ignore()
                return

            # Teminate and process events so onSimulationFinished cleans up
            self.simulation.terminate()
            QApplication.instance().processEvents()

        if self.unsaved_changes:
            if not self.promptSaveChanges():
                # Model changed and user cancelled during prompt
                event.ignore()
                return

        # Remove output directory for this instance
        shutil.rmtree(self.output_dir)

        with open(self.app_data_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(self.config(), f, ensure_ascii=False, indent=4)

        event.accept()

    def onSimulationFinished(self, returncode):
        if returncode != 0:
            if not self.simulation.terminate_flag:
                raise RuntimeError("The simulation completed with errors")
        
            # Clean directory
            shutil.rmtree(self.output_dir)
            self.output_dir.mkdir()
            
            self.wsim_button.setText(" Simulate")
            self.wsim_button.setIcon(QIcon(str(package.dir / "data/play.svg")))
        else:
            self.wcentral_widget.setCurrentWidget(self.wno_chart_placeholder)
            self.wsim_button.setText(" Re-simulate")
            self.wsim_button.setIcon(QIcon(str(package.dir / "data/restart.svg")))
        
        self.wsim_progess_bar.setRange(0, 1)
        self.wsim_progess_bar.reset()

        self.wsim_button.setEnabled(True)
        self.wsim_button.clicked.disconnect(self.actionStopSimulation)
        self.wsim_button.clicked.connect(self.actionStartSimulation)

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
