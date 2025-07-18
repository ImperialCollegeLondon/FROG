"""Provides a widget for choosing the path to a measure script."""

from abc import abstractmethod
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)


class PathWidget(QWidget):
    """A widget containing a text box with a file path and a browse button."""

    def __init__(self, initial_file_path: Path | None = None) -> None:
        """Create a new PathWidget.

        Args:
            initial_file_path: The initial file path to display
        """
        super().__init__()

        self.line_edit = QLineEdit()
        """Indicates the current selected path."""

        if initial_file_path:
            self.line_edit.setText(str(initial_file_path))

        browse = QPushButton("&Browse...")
        browse.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        browse.clicked.connect(self._browse_clicked)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.line_edit)
        layout.addWidget(browse)
        self.setLayout(layout)

    def _browse_clicked(self) -> None:
        filename = self.try_get_path_from_dialog()
        if filename:
            self.set_path(filename)

    @abstractmethod
    def try_get_path_from_dialog(self) -> Path | None:
        """Try to get the file name by raising a dialog."""

    def try_get_path(self) -> Path | None:
        """Try to get the path of the chosen file for this widget.

        If the path hasn't yet been set, a QFileDialog is opened to let the user choose
        one.

        Returns:
            The selected file path or None if the user has cancelled
        """
        txt = self.line_edit.text()
        if txt:
            return Path(txt)

        # ...otherwise the user hasn't chosen a path. Let them do it now.
        filename = self.try_get_path_from_dialog()
        if filename:
            self.set_path(filename)
            return Path(filename)

        # No path selected
        return None

    def set_path(self, path: Path) -> None:
        """Set the path of this widget."""
        self.line_edit.setText(str(path))


class OpenFileWidget(PathWidget):
    """A widget that lets the user choose the path to an existing file."""

    def __init__(
        self,
        initial_file_path: Path | None = None,
        extension: str | None = None,
        **file_dialog_kwargs: Any,
    ) -> None:
        """Create a new OpenFileWidget.

        Args:
            initial_file_path: The initial file path to display
            extension: The extension of the file to open
            file_dialog_kwargs: Arguments to pass to QFileDialog.getOpenFileName
        """
        super().__init__(initial_file_path)
        if extension:
            file_dialog_kwargs["filter"] = f"*.{extension}"
        self.file_dialog_kwargs = file_dialog_kwargs

    def try_get_path_from_dialog(self) -> Path | None:
        """Try to get the path of the file to open by raising a dialog."""
        filename, _ = QFileDialog.getOpenFileName(**self.file_dialog_kwargs)

        return Path(filename) if filename else None


class OpenDirectoryWidget(PathWidget):
    """A widget that lets the user choose the path to an existing directory."""

    def __init__(
        self,
        initial_dir_path: Path | None = None,
        **file_dialog_kwargs: Any,
    ) -> None:
        """Create a new OpenDirectoryWidget.

        Args:
            initial_dir_path: The initial file path to display
            file_dialog_kwargs: Arguments to pass to QFileDialog.getOpenFileName
        """
        super().__init__(initial_dir_path)
        self.file_dialog_kwargs = file_dialog_kwargs

    def try_get_path_from_dialog(self) -> Path | None:
        """Try to get the path of the dir to open by raising a dialog."""
        dir_path = QFileDialog.getExistingDirectory(**self.file_dialog_kwargs)

        return Path(dir_path) if dir_path else None


class SaveFileWidget(PathWidget):
    """A widget that lets the user choose the path to save a file."""

    def __init__(
        self,
        initial_file_path: Path | None = None,
        extension: str | None = None,
        **file_dialog_kwargs: Any,
    ) -> None:
        """Create a new SaveFileWidget.

        Args:
            initial_file_path: The initial file path to display
            extension: The extension of the file to save
            file_dialog_kwargs: Arguments to pass to QFileDialog.getSaveFileName
        """
        super().__init__(initial_file_path)
        if extension:
            file_dialog_kwargs["filter"] = f"*.{extension}"
        self.extension = extension
        self.file_dialog_kwargs = file_dialog_kwargs

    def try_get_path_from_dialog(self) -> Path | None:
        """Try to get the path to save the file to by opening a dialog."""
        filename, _ = QFileDialog.getSaveFileName(**self.file_dialog_kwargs)

        # User cancelled
        if not filename:
            return None

        # Ensure it has the right extension if required
        if self.extension and not filename.lower().endswith(f".{self.extension}"):
            filename += f".{self.extension}"

        return Path(filename)
