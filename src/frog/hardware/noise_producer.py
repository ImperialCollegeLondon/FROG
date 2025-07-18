"""Provides a class for producing random noise."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


class NoiseProducer:
    """A callable object which produces normally distributed noise."""

    def __init__(
        self,
        mean: float = 0.0,
        standard_deviation: float = 1.0,
        type: type = float,
        seed: int | None = 42,
    ) -> None:
        """Create a new NoiseProducer.

        Args:
            mean: The distribution's mean
            standard_deviation: The distribution's standard deviation
            type: The type of the returned value
            seed: Initial random seed (None for random)
        """
        self.rng = np.random.default_rng(seed)
        self.mean = mean
        self.standard_deviation = standard_deviation
        self.type = type

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Return some noise.

        Returns:
            A random number of the specified type.
        """
        return self.type(self.rng.normal(self.mean, self.standard_deviation))

    @classmethod
    def from_parameters(
        cls, parameters: NoiseParameters, type: type = float
    ) -> NoiseProducer:
        """Create a NoiseProducer from a NoiseParameters object."""
        return cls(**asdict(parameters), type=type)


@dataclass
class NoiseParameters:
    """A compact way of expressing arguments to NoiseProducer."""

    mean: float = 0.0
    standard_deviation: float = 1.0
    seed: int | None = 42
