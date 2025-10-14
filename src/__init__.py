"""High-level interfaces for slide generation workflows."""

from .slide_library import SlideLibrary, SlideAsset, PlaceholderSpec
from .slide_models import (
    SlideDocument,
    SlidePage,
    SlidePlaceholderContent,
)
from .slide_generation import SlideContentGenerator
from .slide_document import SlideDocumentStore

__all__ = [
    "SlideLibrary",
    "SlideAsset",
    "PlaceholderSpec",
    "SlideDocument",
    "SlidePage",
    "SlidePlaceholderContent",
    "SlideContentGenerator",
    "SlideDocumentStore",
]
