"""Panel and widgets related to monitoring the interferometer."""
from typing import Dict

from pubsub import pub
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..hardware.em27_diag_autom import EM27Property
from .led_icons import LEDIcon


class EM27Monitor(QGroupBox):
    """Panel containing widgets to view the EM27 properties."""

    def __init__(self) -> None:
        """Creates the attributes required to view properties monitored by the EM27."""
        super().__init__("EM27 SOH Monitor")

        self._val_lineedits: Dict[str, QLineEdit] = {}
        self._data_table: list[EM27Property] = []

        self._poll_light = LEDIcon.create_poll_icon()
        self._poll_light._timer.timeout.connect(self.poll_server)  # type: ignore

        self._create_layouts()

        self._poll_wid_layout.addWidget(QLabel("POLL Server"))
        self._poll_wid_layout.addWidget(self._poll_light)
        self._poll_light.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed  # type: ignore
        )

        self.setLayout(self._layout)

        pub.subscribe(self.begin_polling, "psf27.opened")
        #        pub.subscribe(self.end_polling, "psf27.closed")
        pub.subscribe(self.get_data_table, "psf27.data.send")

    def _create_layouts(self) -> None:
        """Creates layouts to house the widgets."""
        self._poll_wid_layout = QHBoxLayout()
        self._prop_wid_layout = QGridLayout()

        top = QWidget()
        top.setLayout(self._prop_wid_layout)
        bottom = QWidget()
        bottom.setLayout(self._poll_wid_layout)

        self._layout = QVBoxLayout()
        self._layout.addWidget(top)
        self._layout.addWidget(bottom)

    def _get_prop_lineedit(self, prop: EM27Property) -> QLineEdit:
        """Create and populate the widgets for displaying a given property.

        Args:
            prop: the EM27 property to display

        Returns:
            QLineEdit: the QLineEdit widget corresponding to the property
        """
        if prop.name not in self._val_lineedits:
            prop_label = QLabel(prop.name)
            val_lineedit = QLineEdit()
            val_lineedit.setReadOnly(True)
            val_lineedit.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self._val_lineedits[prop.name] = val_lineedit

            num_props = len(self._val_lineedits)
            self._prop_wid_layout.addWidget(prop_label, num_props, 0)
            self._prop_wid_layout.addWidget(val_lineedit, num_props, 1)

        return self._val_lineedits[prop.name]

    def _display_props(self) -> None:
        """Creates and populates the widgets to view the EM27 properties."""
        for prop in self._data_table:
            lineedit = self._get_prop_lineedit(prop)
            lineedit.setText(prop.val_str())

    def get_data_table(self, data: list[EM27Property]):
        """Receive the table containing the property data from the server."""
        self._data_table = data

    def begin_polling(self) -> None:
        """Initiate polling the server."""
        self._poll_light._timer.start(2000)

    def end_polling(self) -> None:
        """Terminate polling the server."""
        self._poll_light._timer.stop()

    def poll_server(self) -> None:
        """Polls the server to obtain the latest values."""
        self._poll_light._flash()
        pub.sendMessage("psf27.data.request")
        self._display_props()


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)

    window = QMainWindow()
    em27_monitor = EM27Monitor()

    window.setCentralWidget(em27_monitor)
    window.show()
    app.exec()
