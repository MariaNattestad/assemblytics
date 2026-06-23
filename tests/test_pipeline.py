"""Regression tests for the Assemblytics pipeline.

Run with: pytest tests/
"""

import os
import tempfile
import pytest

from assemblytics.cli import run
import argparse

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "ecoli")
ECOLI_DELTA = os.path.join(os.path.dirname(__file__), "..", "input_examples", "ecoli.delta.gz")


@pytest.fixture(scope="module")
def ecoli_output():
    with tempfile.TemporaryDirectory() as tmp:
        run(argparse.Namespace(
            delta=ECOLI_DELTA,
            output_dir=tmp,
            unique_length=10000,
            minimum_size=50,
            maximum_size=10000,
            long_range=False,
        ))
        yield tmp


TEXT_FILES = [
    "assemblytics_structural_variants.bed",
    "assemblytics_coords.tab",
    "assemblytics_coords.csv",
    "assemblytics_dot.coords",
    "assemblytics_dot.coords.idx",
    "assemblytics_assembly_stats.txt",
]


@pytest.mark.parametrize("filename", TEXT_FILES)
def test_output_matches_fixture(ecoli_output, filename):
    actual_path = os.path.join(ecoli_output, filename)
    fixture_path = os.path.join(FIXTURES, filename)

    assert os.path.exists(actual_path), f"{filename} was not produced"

    with open(actual_path) as f:
        actual = f.read()
    with open(fixture_path) as f:
        expected = f.read()

    assert actual == expected, f"{filename} differs from fixture"


def test_variants_bed_has_header_and_variants(ecoli_output):
    path = os.path.join(ecoli_output, "assemblytics_structural_variants.bed")
    with open(path) as f:
        lines = f.readlines()
    assert lines[0].startswith("#reference"), "BED file missing header"
    assert len(lines) > 1, "No variants called"


def test_dot_coords_sections(ecoli_output):
    idx_path = os.path.join(ecoli_output, "assemblytics_dot.coords.idx")
    with open(idx_path) as f:
        content = f.read()
    for section in ("#ref", "#query", "#overview"):
        assert section in content, f"Missing {section} section in .coords.idx"


def test_all_expected_files_produced(ecoli_output):
    expected = [
        "assemblytics_structural_variants.bed",
        "assemblytics_coords.csv",
        "assemblytics_coords.tab",
        "assemblytics_assembly_stats.txt",
        "assemblytics_dot.coords",
        "assemblytics_dot.coords.idx",
        "assemblytics_results.zip",
    ]
    for f in expected:
        assert os.path.exists(os.path.join(ecoli_output, f)), f"Missing expected output: {f}"
