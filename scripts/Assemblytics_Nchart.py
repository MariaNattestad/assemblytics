#!/usr/bin/env python3

import sys
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

def bp_format(num):
    if num > 1000000000:
        return "{:,.3f} Gbp".format(num / 1000000000).rstrip('0').rstrip('.')
    elif num > 1000000:
        return "{:,.3f} Mbp".format(num / 1000000).rstrip('0').rstrip('.')
    elif num > 1000:
        return "{:,.3f} Kbp".format(num / 1000).rstrip('0').rstrip('.')
    else:
        return "{:,} bp".format(int(num))

def run(prefix):
    # Instead of reading .coords.ref.genome and .coords.query.genome, 
    # we'll read .coords.tab and generate the data ourselves.
    coords_tab = prefix + ".coords.tab"
    if not os.path.exists(coords_tab):
        print(f"File {coords_tab} not found.")
        return

    try:
        # Columns in coords.tab: ref_start, ref_end, query_start, query_end, ref_length, query_length, ref, query
        df = pd.read_csv(coords_tab, sep="\t", header=None, 
                         names=["ref_start", "ref_end", "query_start", "query_end", 
                                "ref_full_length", "query_full_length", "ref", "query"])
    except Exception as e:
        print(f"Error reading {coords_tab}: {e}")
        return

    # Extract unique reference sequences and their lengths
    ref_data = df[["ref", "ref_full_length"]].drop_duplicates().sort_values("ref_full_length", ascending=False)
    ref_data.columns = ["name", "length"]
    
    # Extract unique query sequences and their lengths
    query_data = df[["query", "query_full_length"]].drop_duplicates().sort_values("query_full_length", ascending=False)
    query_data.columns = ["name", "length"]

    genome_length = max(ref_data["length"].sum(), query_data["length"].sum())

    # Calculate cumulative distributions
    ref_cumsum = pd.DataFrame({
        "NG": (ref_data["length"].cumsum() / genome_length * 100),
        "contig_length": ref_data["length"],
        "contig_source": "Reference"
    })

    query_cumsum = pd.DataFrame({
        "NG": (query_data["length"].cumsum() / genome_length * 100),
        "contig_length": query_data["length"],
        "contig_source": "Query"
    })

    both_plot = pd.concat([ref_cumsum, query_cumsum])

    # Add zeros for the start of the plot
    ref_cumsum_0 = pd.concat([pd.DataFrame({"NG": [0], "contig_length": [ref_cumsum["contig_length"].max()], "contig_source": ["Reference"]}), ref_cumsum])
    query_cumsum_0 = pd.concat([pd.DataFrame({"NG": [0], "contig_length": [query_cumsum["contig_length"].max()], "contig_source": ["Query"]}), query_cumsum])
    
    with_zeros = pd.concat([ref_cumsum_0, query_cumsum_0])

    plt.figure(figsize=(8, 8))
    colors = {"Reference": "limegreen", "Query": "blue"}

    if len(with_zeros) > 2:
        for source in ["Reference", "Query"]:
            data = with_zeros[with_zeros["contig_source"] == source]
            plt.step(data["NG"], data["contig_length"], where='post', color=colors[source], label=source, linewidth=1.5, alpha=0.5)
            
            points = both_plot[both_plot["contig_source"] == source]
            plt.scatter(points["NG"], points["contig_length"], color=colors[source], s=20, alpha=0.5)
    else:
        for source in ["Reference", "Query"]:
            points = both_plot[both_plot["contig_source"] == source]
            plt.scatter(points["NG"], points["contig_length"], color=colors[source], s=40, alpha=0.5, label=source)

    plt.yscale('log')
    plt.xlim(0, 100)
    plt.ylim(1, genome_length * 1.1)
    
    plt.xlabel(f"NG(x)% where 100% = {bp_format(genome_length)}")
    plt.ylabel("Sequence length")
    plt.title("Cumulative sequence length")
    plt.legend(title="Assembly")
    plt.grid(True, which="both", ls="-", alpha=0.2)

    plt.tight_layout()
    for fmt in ['png', 'pdf']:
        plt.savefig(f"{prefix}.Assemblytics.Nchart.{fmt}", dpi=200)
    plt.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: Assemblytics_Nchart.py prefix")
        sys.exit(1)
    run(sys.argv[1])
