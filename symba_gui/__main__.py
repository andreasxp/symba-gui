import sys
from argparse import ArgumentParser
from subprocess import Popen
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        menu_bar = self.menuBar()

        menu_file = menu_bar.addMenu("File")
        
        action_new = menu_file.addAction("New Simulation")
        action_new.triggered.connect(self.actionNew)

        action_new_window = menu_file.addAction("New Window")
        action_new_window.triggered.connect(self.actionNewWindow)

        menu_file.addSeparator()
        menu_file.addAction("Open...")
        menu_file.addSeparator()
        menu_file.addAction("Save")
        menu_file.addAction("Save As...")
        menu_file.addSeparator()
        action_exit = menu_file.addAction("Exit")
        action_exit.triggered.connect(self.actionExit)

    def actionNew(self):
        pass

    def actionNewWindow(self):
        """Start a new experiment. Opens a new window.
        
        This process launches a new simulation window by creating a detached process. The way the process is created
        depends on sys.argv[0] (what is the origin of this process).
        """
        pos_x = self.pos().x() + 40
        pos_y = self.pos().y() + 40
        cli_args = ["--window-pos", f"{pos_x},{pos_y}"]

        if sys.argv[0].endswith(".py"):
            # Application launched with python
            Popen([sys.executable, sys.argv[0]] + cli_args)
        else:
            # Assume the application was launched using an executable
            Popen([sys.argv[0]] + cli_args)
        
    def actionExit(self):
        self.close()


def main():
    print(sys.argv[0])
    parser = ArgumentParser()
    parser.add_argument("--window-pos", help="new window position on the screen")

    args = parser.parse_args()
    if args.window_pos is not None:
        args.window_pos = [int(x) for x in args.window_pos.split(",")]

    app = QApplication(sys.argv)

    main_window = MainWindow()
    if args.window_pos is not None:
        main_window.move(*args.window_pos)

    main_window.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())