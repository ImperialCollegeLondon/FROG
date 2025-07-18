"""Code for FROG's documentation viewer window."""

from importlib import resources
from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow, QToolBar, QVBoxLayout, QWidget


class DocsViewer(QAction):
    """A window for viewing documentation."""

    def __init__(self, parent: QObject) -> None:
        """Create a menu item for opening documentation in a new window.

        Args:
            parent: the menu on which to place the menu item
        """
        super().__init__("Open user guide", parent)
        self.triggered.connect(self.show_docs)

    def show_docs(self) -> None:
        """Create the documentation in a new window."""
        self.docs_window = self.create_docs_window()
        self.docs_window.show()

    def create_docs_window(self) -> QMainWindow:
        """Create a new window displaying the documentation.

        Returns:
            A main window showing the html documentation.
        """
        docs_window = QMainWindow()
        docs_window.setWindowTitle("User Guide")

        toolbar = QToolBar()
        toolbar.setMovable(False)
        home_btn = toolbar.addAction("Home")
        back_btn = toolbar.addAction("Back")
        forward_btn = toolbar.addAction("Forward")
        docs_window.addToolBar(toolbar)

        docs_path = resources.files("docs")
        self.docs_home = Path(str(docs_path.joinpath("user_guide.html")))
        if not self.docs_home.exists():
            self.docs_home = Path(str(docs_path.joinpath("fallback.html")))
        self.browser = QWebEngineView()
        self._open_homepage()
        home_btn.triggered.connect(self._open_homepage)
        back_btn.triggered.connect(self.browser.back)
        forward_btn.triggered.connect(self.browser.forward)

        layout = QVBoxLayout()
        layout.addWidget(self.browser)

        central = QWidget()
        central.setLayout(layout)

        docs_window.setCentralWidget(central)

        return docs_window

    def _open_homepage(self) -> None:
        """Go to documentation home page."""
        self.browser.load(self.docs_home.as_uri())
