#!/usr/bin/env python3

"""Python orchestrator for the Assemblytics pipeline."""

import argparse
import io
import os
import sys
import zipfile

from .dot_prep import index_for_dot
from .dotplot import run as run_dotplot
from .index import run as run_index
from .nchart import run as run_nchart
from .summary import SVtable as run_summary
from .uniq_anchor import run as run_uniq_anchor
from .variant_charts import run as run_variant_charts
from .variants import run as run_variants


USAGE = "assemblytics -d delta -o output_dir -l unique_length -min min_size -max max_size"


def log_progress(log_file, message):
    with open(log_file, "a") as log:
        log.write(message + "\n")


def fail(log_file, step, message, exit_code=1):
    log_progress(log_file, step)
    sys.exit(exit_code)


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
    long_range = getattr(args, "long_range", False)

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
    reference_lengths, fields_by_query = run_uniq_anchor(
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

    print("2. Finding structural variants")
    combined_path = os.path.join(output_dir, "assemblytics_structural_variants.bed")
    long_range_path = os.path.join(output_dir, "assemblytics_long_range_variants.bed") if long_range else None
    run_variants(filtered_delta, minimum_size, maximum_size, minimum_size, combined_path, long_range_path)
    if not os.path.exists(combined_path):
        fail(
            log_file,
            "VARIANTS,FAIL,Step 2: variants.py failed: "
            "Possible problem with Python on server.",
        )
    print("FILE_READY:" + os.path.basename(combined_path))
    if long_range:
        print("FILE_READY:" + os.path.basename(long_range_path))

    log_progress(
        log_file,
        "VARIANTS,DONE,Step 2: variants.py completed successfully. "
        "Now generating figures and summary statistics.",
    )

    print("3. Index coordinates and generate summary statistics")
    run_index(
        argparse.Namespace(
            coords=os.path.join(output_dir, "assemblytics_coords.csv"),
            out=output_dir,
        )
    )
    run_summary_to_file(output_dir, minimum_size, maximum_size)
    print("FILE_READY:assemblytics_structural_variants_summary.txt")

    print("4. Generating figures")
    run_variant_charts(output_dir, minimum_size, maximum_size)
    # Charts are ready incrementally too
    charts = [f for f in os.listdir(output_dir) if f.startswith("assemblytics_size_distributions") and f.endswith(".png")]
    for chart in charts:
        print("FILE_READY:" + chart)

    run_dotplot(output_dir)
    print("FILE_READY:assemblytics_dotplot_filtered.png")

    run_nchart(output_dir)
    print("FILE_READY:assemblytics_nchart.png")

    print("5. Preparing interactive Dot plot")
    dot_prefix = os.path.join(output_dir, "assemblytics_dot")
    index_for_dot(reference_lengths, fields_by_query, dot_prefix, 1000)
    print("FILE_READY:assemblytics_dot.coords")
    print("FILE_READY:assemblytics_dot.coords.idx")

    zip_results(output_dir)
    print("FILE_READY:assemblytics_results.zip")

    summary_path = os.path.join(output_dir, "assemblytics_structural_variants_summary.txt")
    with open(summary_path) as summary:
        if "Total" not in summary.read():
            fail(log_file, "SUMMARY,FAIL,Step 3: summary.py failed")

    log_progress(
        log_file,
        "SUMMARY,DONE,Step 3: summary.py completed successfully",
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
    parser.add_argument(
        "--long-range",
        dest="long_range",
        action="store_true",
        help=(
            "Also report long-range and inter-chromosomal candidate variants (events bigger "
            "than --maximum_size, or spanning two different reference chromosomes) to a "
            "separate assemblytics_long_range_variants.bed file. These are usually caused by "
            "misassemblies, but can also represent real translocations or other large-scale "
            "rearrangements, so they're kept out of the main results by default and require "
            "manual review."
        ),
    )
    parser.set_defaults(func=run)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
