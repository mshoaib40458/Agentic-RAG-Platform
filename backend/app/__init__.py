"""Agentic RAG Platform backend application package."""

import os

# The ML stack here uses only the PyTorch path. If a host interpreter also has
# TensorFlow/JAX installed, transformers/datasets import them eagerly, adding
# ~50s and hundreds of MB to startup for no benefit. Disable them unless the
# operator explicitly opts in (an external USE_TF/USE_FLAX wins via setdefault).
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

__version__ = "0.1.0"
