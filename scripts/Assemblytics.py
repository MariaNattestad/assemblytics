#!/usr/bin/env python3

"""Python orchestrator for the Assemblytics pipeline."""

import argparse
import io
import os
import sys
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from Assemblytics_between_alignments import run as run_between_alignments
from Assemblytics_dotplot import run as run_dotplot
from Assemblytics_index import run as run_index
from Assemblytics_Nchart import run as run_nchart
from Assemblytics_summary import SVtable as run_summary
from Assemblytics_uniq_anchor import run as run_uniq_anchor
from Assemblytics_variant_charts import run as run_variant_charts
from Assemblytics_within_alignment import run as run_within_alignment


USAGE = "Assemblytics delta output_prefix unique_length_required min_size max_size"

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


def combine_variants(output_prefix):
    combined_path = output_prefix + ".Assemblytics_structural_variants.bed"
    with open(combined_path, "w") as combined:
        combined.write(STRUCTURAL_VARIANTS_HEADER + "\n")
        for suffix in ("variants_within_alignments.bed", "variants_between_alignments.bed"):
            path = output_prefix + "." + suffix
            if os.path.exists(path) and os.path.getsize(path) > 0:
                with open(path) as variants:
                    combined.write(variants.read())
    return combined_path


def write_coords_genome_files(output_prefix):
    coords_tab = output_prefix + ".coords.tab"
    ref_genome = output_prefix + ".coords.ref.genome"
    query_genome = output_prefix + ".coords.query.genome"

    ref_entries = {}
    query_entries = {}
    with open(coords_tab) as coords:
        for line in coords:
            fields = line.split()
            ref_entries[fields[6]] = int(fields[4])
            query_entries[fields[7]] = int(fields[5])

    with open(ref_genome, "w") as ref_out:
        for name, length in sorted(ref_entries.items(), key=lambda item: item[1], reverse=True):
            ref_out.write("%s\t%d\n" % (name, length))

    with open(query_genome, "w") as query_out:
        for name, length in sorted(query_entries.items(), key=lambda item: item[1], reverse=True):
            query_out.write("%s\t%d\n" % (name, length))


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


def write_variant_preview(output_prefix, num_lines=10):
    bed_path = output_prefix + ".Assemblytics_structural_variants.bed"
    preview_path = output_prefix + ".variant_preview.txt"
    with open(bed_path) as bed:
        preview_lines = [line.rstrip("\n") for index, line in enumerate(bed) if index < num_lines]
    
    formatted_preview = format_column_table(preview_lines)
    with open(preview_path, "w") as preview:
        preview.write(formatted_preview)


def zip_results(output_prefix):
    zip_path = output_prefix + ".Assemblytics_results.zip"
    zip_filename = os.path.basename(zip_path)
    prefix_dir = os.path.dirname(output_prefix)
    prefix_name = os.path.basename(output_prefix)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename in os.listdir(prefix_dir or "."):
            if filename.startswith(prefix_name + ".Assemblytics") and filename != zip_filename:
                archive.write(os.path.join(prefix_dir, filename), filename)


def run_summary_to_file(output_prefix, minimum_size, maximum_size):
    summary_path = output_prefix + ".Assemblytics_structural_variants.summary"
    bed_path = output_prefix + ".Assemblytics_structural_variants.bed"
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
    output_prefix = args.output_prefix
    unique_length = args.unique_length
    minimum_size = args.minimum_size
    maximum_size = args.maximum_size

    print("Input delta file:", delta, file=sys.stderr)
    print("Output prefix:", output_prefix, file=sys.stderr)
    print("Unique anchor length:", unique_length, file=sys.stderr)
    print("Minimum variant size to call:", minimum_size, file=sys.stderr)
    print("Maximum variant size to call:", maximum_size, file=sys.stderr)

    output_dir = os.path.dirname(output_prefix)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    log_file = os.path.join(output_dir, "progress.log") if output_dir else "progress.log"
    print("Logging progress updates in", log_file, file=sys.stderr)

    log_progress(log_file, os.path.basename(output_prefix))
    log_progress(log_file, "STARTING,DONE,Starting unique anchor filtering.")

    print("1. Filter delta file", file=sys.stderr)
    run_uniq_anchor(
        argparse.Namespace(
            delta=delta,
            out=output_prefix,
            unique_length=unique_length,
            keep_small_uniques=True,
        )
    )

    filtered_delta = "{}.Assemblytics.unique_length_filtered_l{}.delta.gz".format(
        output_prefix, unique_length
    )
    if not os.path.exists(filtered_delta):
        fail(
            log_file,
            "UNIQFILTER,FAIL,Step 1: Assemblytics_uniq_anchor.py failed: "
            "Possible problem with Python or Python packages on server.",
        )

    log_progress(
        log_file,
        "UNIQFILTER,DONE,Step 1: Assemblytics_uniq_anchor.py completed successfully. "
        "Now finding variants between alignments.",
    )

    print("2. Finding variants between alignments", file=sys.stderr)
    between_path = output_prefix + ".variants_between_alignments.bed"
    run_between_alignments(
        argparse.Namespace(
            coordsfile=output_prefix + ".coords.tab",
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
            "BETWEEN,FAIL,Step 2: Assemblytics_between_alignments.py failed: "
            "Possible problem with Python on server.",
        )

    log_progress(
        log_file,
        "BETWEEN,DONE,Step 2: Assemblytics_between_alignments.py completed successfully. "
        "Now finding variants within alignments.",
    )

    print("3. Finding variants within alignments", file=sys.stderr)
    within_path = output_prefix + ".variants_within_alignments.bed"
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
            "WITHIN,FAIL,Step 3: Assemblytics_within_alignment.py failed: "
            "Possible problem before this step or with Python on server.",
        )

    log_progress(
        log_file,
        "WITHIN,DONE,Step 3: Assemblytics_within_alignment.py completed successfully. "
        "Now combining the two sets of variants together.",
    )

    print("4. Combine variants between and within alignments", file=sys.stderr)
    combined_path = combine_variants(output_prefix)
    if not os.path.exists(combined_path):
        fail(log_file, "COMBINE,FAIL,Step 4: combining variants failed")

    log_progress(
        log_file,
        "COMBINE,DONE,Step 4: Variants combined successfully. "
        "Now generating figures and summary statistics.",
    )

    print("5. Index coordinates and generate summary statistics", file=sys.stderr)
    run_index(
        argparse.Namespace(
            coords=output_prefix + ".coords.csv",
            out=output_prefix,
        )
    )
    write_coords_genome_files(output_prefix)
    run_summary_to_file(output_prefix, minimum_size, maximum_size)
    write_variant_preview(output_prefix)

    print("6. Generating figures", file=sys.stderr)
    run_variant_charts(output_prefix, minimum_size, maximum_size)
    run_dotplot(output_prefix)
    run_nchart(output_prefix)

    zip_results(output_prefix)

    summary_path = output_prefix + ".Assemblytics_structural_variants.summary"
    with open(summary_path) as summary:
        if "Total" not in summary.read():
            fail(log_file, "SUMMARY,FAIL,Step 5: Assemblytics_summary.py failed")

    log_progress(
        log_file,
        "SUMMARY,DONE,Step 5: Assemblytics_summary.py completed successfully",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Assemblytics structural variant detection pipeline",
        usage=USAGE,
    )
    parser.add_argument("-d", "--delta", help="MUMmer delta file (.delta or .delta.gz)", required=True)
    parser.add_argument("-o", "--output_prefix", help="Output file prefix (may include a directory path)", required=True)
    parser.add_argument("-l", "--unique_length", type=int, default=10000, help="Unique anchor length requirement (default: 10000)")
    parser.add_argument("-min", "--minimum_size", type=int, default=50, help="Minimum variant size to call (default: 50)")
    parser.add_argument("-max", "--maximum_size", type=int, default=10000, help="Maximum variant size to call (default: 10000)")
    parser.set_defaults(func=run)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
