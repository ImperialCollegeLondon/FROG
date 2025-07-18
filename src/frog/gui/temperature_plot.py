"""Panel showing a plot of temperatures."""

from collections.abc import Sequence
from datetime import datetime
from functools import partial

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from pubsub import pub
from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QPushButton,
)

from frog.config import (
    TEMPERATURE_MONITOR_COLD_BB_IDX,
    TEMPERATURE_MONITOR_HOT_BB_IDX,
    TEMPERATURE_MONITOR_POLL_INTERVAL,
    TEMPERATURE_MONITOR_TOPIC,
    TEMPERATURE_PLOT_TIME_RANGE,
)


class TemperaturePlot(QGroupBox):
    """Widgets to view the temperature properties."""

    def __init__(self) -> None:
        """Creates a panel with a graph to monitor the blackbody temperatures."""
        super().__init__("BB Monitor")

        layout = self._create_controls()
        self.setLayout(layout)

        pub.subscribe(
            self._plot_bb_temps, f"device.{TEMPERATURE_MONITOR_TOPIC}.data.response"
        )

    def _create_controls(self) -> QGridLayout:
        """Creates the overall layout for the panel.

        Returns:
            QGridLayout: The layout containing the figure.
        """
        layout = QGridLayout()
        self._btns = {"hot": QPushButton("Hot BB"), "cold": QPushButton("Cold BB")}
        self._btns["hot"].setCheckable(True)
        self._btns["cold"].setCheckable(True)
        self._btns["hot"].setChecked(True)
        self._btns["cold"].setChecked(True)
        self._btns["hot"].clicked.connect(
            partial(self._toggle_axis_visibility, name="hot")
        )
        self._btns["cold"].clicked.connect(
            partial(self._toggle_axis_visibility, name="cold")
        )
        self._btns["hot"].setMaximumWidth(80)
        self._btns["cold"].setMaximumWidth(80)

        self._create_figure()
        self._canvas.setMinimumSize(QSize(640, 120))

        layout.addWidget(self._btns["hot"], 0, 0)
        layout.addWidget(self._btns["cold"], 1, 0)
        layout.addWidget(self._canvas, 0, 1, 3, 1)

        return layout

    def _create_figure(self) -> None:
        """Creates the matplotlib figure to be contained within the panel."""
        self._figure, ax = plt.subplots(constrained_layout=True)
        self._ax = {"hot": ax}
        self._canvas = FigureCanvasQTAgg(self._figure)

        self._figure_num_pts = int(
            TEMPERATURE_PLOT_TIME_RANGE / TEMPERATURE_MONITOR_POLL_INTERVAL
        )

        nans = np.full([self._figure_num_pts], np.nan)

        hot_colour = "r"
        cold_colour = "b"

        self._ax["hot"].plot(nans, nans, color=hot_colour, linestyle="-")
        self._ax["hot"].set_ylabel("HOT BB", color=hot_colour)

        max_ticks = 8
        self._ax["hot"].xaxis.set_major_locator(ticker.MaxNLocator(nbins=max_ticks - 1))
        self._ax["hot"].xaxis.set_major_formatter(
            ticker.FuncFormatter(self._xtick_format_fcn)
        )

        self._ax["cold"] = self._ax["hot"].twinx()
        self._ax["cold"].plot(nans, nans, color=cold_colour, linestyle="-")
        self._ax["cold"].set_ylabel("COLD BB", color=cold_colour)

        self._canvas.draw()

    def _toggle_axis_visibility(self, name: str) -> None:
        """Shows or hides individual blackbody temperature plots.

        Args:
            name: the name of the blackbody whose data visibility is toggled
        """
        state = self._btns[name].isChecked()
        self._ax[name].yaxis.set_visible(state)
        self._ax[name].lines[0].set_visible(state)

        self._make_axes_sensible()
        self._canvas.draw()

    def _update_figure(
        self, new_time: float, new_hot_data: float, new_cold_data: float
    ) -> None:
        """Updates the matplotlib figure to be contained within the panel.

        Args:
            new_time: the time at which the new data were retrieved
            new_hot_data: the new temperature of the hot blackbody
            new_cold_data: the new temperature of the cold blackbody
        """
        time = np.array(self._ax["hot"].lines[0].get_xdata())
        hot_data = np.array(self._ax["hot"].lines[0].get_ydata())
        cold_data = np.array(self._ax["cold"].lines[0].get_ydata())

        # Remove first element and append a new one
        time = np.array([*time[1:], new_time])
        hot_data = np.array([*hot_data[1:], new_hot_data])
        cold_data = np.array([*cold_data[1:], new_cold_data])

        self._ax["hot"].lines[0].set_xdata(time)
        self._ax["hot"].lines[0].set_ydata(hot_data)
        self._ax["cold"].lines[0].set_xdata(time)
        self._ax["cold"].lines[0].set_ydata(cold_data)

        self._make_axes_sensible()

        self._canvas.draw()

    def _xtick_format_fcn(self, val: float, loc: int) -> str:
        """Convert x axis tick labels from timestamp to clock format.

        Args:
            val: value of the tick whose label is being formatted
            loc: location of the tick on the axis

        Returns:
            formatted string to display as x tick label
        """
        return datetime.fromtimestamp(max(val, 0)).strftime("%H:%M:%S")

    def _make_axes_sensible(self) -> None:
        """Rescales the y axes for the the blackbody temperatures."""
        # Rescale limits to account for new data
        self._ax["hot"].relim()
        self._ax["cold"].relim()
        self._ax["hot"].autoscale()
        self._ax["cold"].autoscale()

    def _plot_bb_temps(self, time: datetime, temperatures: Sequence) -> None:
        """Extract blackbody temperatures and plot them.

        Args:
            time: the time that the temperatures were read
            temperatures: the list of current temperatures
        """
        hot_bb_temp = float(temperatures[TEMPERATURE_MONITOR_HOT_BB_IDX])
        cold_bb_temp = float(temperatures[TEMPERATURE_MONITOR_COLD_BB_IDX])

        self._update_figure(time.timestamp(), hot_bb_temp, cold_bb_temp)
