__version__ = "0.0.1"
from ._widget import ExampleQWidget, example_magic_widget

from .oligoAnalysisFolder import oligoAnalysisFolder
from .oligoAnalysis import oligoAnalysis
from .oligoAnalysis import imageChannels  # enum with cyto and dapi
from ._cellpose import runModelOnImage
from .interface.oligoInterface import oligoInterface  # order matters

__all__ = (
    "ExampleQWidget",
    "example_magic_widget",
)
