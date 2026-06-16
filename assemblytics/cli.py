#!/usr/bin/env python3

"""Python orchestrator for the Assemblytics pipeline."""

import argparse
import io
import os
import sys
import zipfile

from .between_alignments import run as run_between_alignments
from .dotplot import run as run_dotplot
from .index import run as run_index
from .nchart import run as run_nchart
from .summary import SVtable as run_summary
from .uniq_anchor import run as run_uniq_anchor
from .variant_charts import run as run_variant_charts
from .within_alignment import run as run_within_alignment


USAGE = "assemblytics -d delta -o output_dir -l unique_length -min min_size -max max_size"

STRUCTURAL_VARIANTS_HEADER = (
    "#reference\tref_start\tref_stop\tID\tsize\tstrand\ttype\t"
    "ref_gap_size\tquery_gap_size\tquery_coordinates\tmethod"
)


def log_progress(log_file, message):
    with open(log_file, "a") as log:
        log.write(message + "\n")


def fail(log_file, step, message, exit_code=1):
    log_progress(log_file, step)
    sys.exit(exit_code)


def combine_variants(output_dir):
    combined_path = os.path.join(output_dir, "assemblytics_structural_variants.bed")
    with open(combined_path, "w") as combined:
        combined.write(STRUCTURAL_VARIANTS_HEADER + "\n")
        for name in ("assemblytics_variants_within_alignments.bed", "assemblytics_variants_between_alignments.bed"):
            path = os.path.join(output_dir, name)
            if os.path.exists(path) and os.path.getsize(path) > 0:
                with open(path) as variants:
                    combined.write(variants.read())
    return combined_path


def format_column_table(lines):
    if not lines:
        return ""
    # Split lines into fields
    table = [line.split("\t") for line in lines]
    # Calculate max width for each column
    num_cols = max(len(row) for row in table)
    col_widths = [0] * num_cols
    for row in table:
        for i, field in enumerate(row):
            col_widths[i] = max(col_widths[i], len(field))

    # Format rows
    formatted_rows = []
    for row in table:
        formatted_row = "  ".join(field.ljust(col_widths[i]) for i, field in enumerate(row))
        formatted_rows.append(formatted_row)
    return "\n".join(formatted_rows) + "\n"


def write_variant_preview(output_dir, num_lines=10):
    bed_path = os.path.join(output_dir, "assemblytics_structural_variants.bed")
    preview_path = os.path.join(output_dir, "assemblytics_variant_preview.txt")
    with open(bed_path) as bed:
        preview_lines = [line.rstrip("\n") for index, line in enumerate(bed) if index < num_lines]

    formatted_preview = format_column_table(preview_lines)
    with open(preview_path, "w") as preview:
        preview.write(formatted_preview)


def zip_results(output_dir):
    zip_path = os.path.join(output_dir, "assemblytics_results.zip")
    zip_filename = os.path.basename(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename in os.listdir(output_dir):
            if filename.startswith("assemblytics_") and filename != zip_filename:
                archive.write(os.path.join(output_dir, filename), filename)


def run_summary_to_file(output_dir, minimum_size, maximum_size):
    summary_path = os.path.join(output_dir, "assemblytics_structural_variants_summary.txt")
    bed_path = os.path.join(output_dir, "assemblytics_structural_variants.bed")
    summary_args = argparse.Namespace(
        file=bed_path,
        minimum_variant_size=minimum_size,
        maximum_variant_size=maximum_size,
    )
    buffer = io.StringIO()
    stdout = sys.stdout
    sys.stdout = buffer
    try:
        run_summary(summary_args)
    finally:
        sys.stdout = stdout
    with open(summary_path, "w") as summary:
        summary.write(buffer.getvalue())


def run(args):
    delta = args.delta
    output_dir = args.output_dir
    unique_length = args.unique_length
    minimum_size = args.minimum_size
    maximum_size = args.maximum_size

    print("Input delta file:", delta)
    print("Output directory:", output_dir)
    print("Unique anchor length:", unique_length)
    print("Minimum variant size to call:", minimum_size)
    print("Maximum variant size to call:", maximum_size)

    os.makedirs(output_dir, exist_ok=True)

    log_file = os.path.join(output_dir, "assemblytics_progress.log")
    print("Logging progress updates in", log_file)

    log_progress(log_file, "STARTING,DONE,Starting unique anchor filtering.")

    print("1. Filter delta file")
    run_uniq_anchor(
        argparse.Namespace(
            delta=delta,
            out=output_dir,
            unique_length=unique_length,
            keep_small_uniques=True,
        )
    )
    print("FILE_READY:assemblytics_assembly_stats.txt")
    print("FILE_READY:assemblytics_coords.tab")
    print("FILE_READY:assemblytics_coords.csv")

    filtered_delta = os.path.join(output_dir, "assemblytics_unique_length_filtered_l{}.delta.gz".format(unique_length))
    if not os.path.exists(filtered_delta):
        fail(
            log_file,
            "UNIQFILTER,FAIL,Step 1: uniq_anchor.py failed: "
            "Possible problem with Python or Python packages on server.",
        )
    print("FILE_READY:" + os.path.basename(filtered_delta))

    log_progress(
        log_file,
        "UNIQFILTER,DONE,Step 1: uniq_anchor.py completed successfully. "
        "Now finding variants between alignments.",
    )

    print("2. Finding variants between alignments")
    between_path = os.path.join(output_dir, "assemblytics_variants_between_alignments.bed")
    run_between_alignments(
        argparse.Namespace(
            coordsfile=os.path.join(output_dir, "assemblytics_coords.tab"),
            minimum_event_size=minimum_size,
            maximum_event_size=maximum_size,
            chromosome_filter="all-chromosomes",
            longrange_filter="exclude-longrange",
            output_file="bed",
            output_path=between_path,
        )
    )
    if not os.path.exists(between_path):
        fail(
            log_file,
            "BETWEEN,FAIL,Step 2: between_alignments.py failed: "
            "Possible problem with Python on server.",
        )
    print("FILE_READY:" + os.path.basename(between_path))

    log_progress(
        log_file,
        "BETWEEN,DONE,Step 2: between_alignments.py completed successfully. "
        "Now finding variants within alignments.",
    )

    print("3. Finding variants within alignments")
    within_path = os.path.join(output_dir, "assemblytics_variants_within_alignments.bed")
    run_within_alignment(
        argparse.Namespace(
            delta=filtered_delta,
            minimum_variant_size=minimum_size,
            output_path=within_path,
        )
    )
    if not os.path.exists(within_path):
        fail(
            log_file,
            "WITHIN,FAIL,Step 3: within_alignment.py failed: "
            "Possible problem before this step or with Python on server.",
        )
    print("FILE_READY:" + os.path.basename(within_path))

    log_progress(
        log_file,
        "WITHIN,DONE,Step 3: within_alignment.py completed successfully. "
        "Now combining the two sets of variants together.",
    )

    print("4. Combine variants between and within alignments")
    combined_path = combine_variants(output_dir)
    if not os.path.exists(combined_path):
        fail(log_file, "COMBINE,FAIL,Step 4: combining variants failed")
    print("FILE_READY:" + os.path.basename(combined_path))

    log_progress(
        log_file,
        "COMBINE,DONE,Step 4: Variants combined successfully. "
        "Now generating figures and summary statistics.",
    )

    print("5. Index coordinates and generate summary statistics")
    run_index(
        argparse.Namespace(
            coords=os.path.join(output_dir, "assemblytics_coords.csv"),
            out=output_dir,
        )
    )
    run_summary_to_file(output_dir, minimum_size, maximum_size)
    write_variant_preview(output_dir)
    print("FILE_READY:assemblytics_structural_variants_summary.txt")
    print("FILE_READY:assemblytics_variant_preview.txt")

    print("6. Generating figures")
    run_variant_charts(output_dir, minimum_size, maximum_size)
    # Charts are ready incrementally too
    charts = [f for f in os.listdir(output_dir) if f.startswith("assemblytics_size_distributions") and f.endswith(".png")]
    for chart in charts:
        print("FILE_READY:" + chart)

    run_dotplot(output_dir)
    print("FILE_READY:assemblytics_dotplot_filtered.png")

    run_nchart(output_dir)
    print("FILE_READY:assemblytics_nchart.png")

    zip_results(output_dir)
    print("FILE_READY:assemblytics_results.zip")

    summary_path = os.path.join(output_dir, "assemblytics_structural_variants_summary.txt")
    with open(summary_path) as summary:
        if "Total" not in summary.read():
            fail(log_file, "SUMMARY,FAIL,Step 5: summary.py failed")

    log_progress(
        log_file,
        "SUMMARY,DONE,Step 5: summary.py completed successfully",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Assemblytics structural variant detection pipeline",
        usage=USAGE,
    )
    parser.add_argument("-d", "--delta", help="MUMmer delta file (.delta or .delta.gz)", required=True)
    parser.add_argument("-o", "--output_dir", help="Output directory for assemblytics_* result files (default: current directory)", default=".")
    parser.add_argument("-l", "--unique_length", type=int, default=10000, help="Unique anchor length requirement (default: 10000)")
    parser.add_argument("-min", "--minimum_size", type=int, default=50, help="Minimum variant size to call (default: 50)")
    parser.add_argument("-max", "--maximum_size", type=int, default=10000, help="Maximum variant size to call (default: 10000)")
    parser.set_defaults(func=run)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
