#!/usr/bin/env python3

import sys
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

def run(prefix):
    filename = prefix + ".oriented_coords.csv"
    plot_output_filename = prefix + ".Assemblytics.Dotplot_filtered"
    plot_title = "Dot plot of Assemblytics filtered alignments"

    if not os.path.exists(filename):
        print(f"File {filename} not found.")
        return

    coords = pd.read_csv(filename)

    if len(coords) > 100000:
        coords = coords.head(100000)

    coords['ref'] = coords['ref'].astype(str)
    coords['query'] = coords['query'].astype(str)

    # Ordering chromosomes
    ordered_common_names = [str(i) for i in range(1, 101)] + \
                           [f"chr{i}" for i in range(1, 101)] + \
                           [f"Chr{i}" for i in range(1, 101)] + \
                           ["X", "Y", "M", "MT", "Chr0", "chr0", "0"]
    
    unique_refs = coords['ref'].unique()
    all_refs_ordered = [r for r in ordered_common_names if r in unique_refs] + \
                       [r for r in unique_refs if r not in ordered_common_names]
    
    coords['ref'] = pd.Categorical(coords['ref'], categories=all_refs_ordered, ordered=True)
    coords = coords.sort_values('ref')

    # Get chromosome lengths and calculate offsets
    chr_lengths = coords.groupby('ref')['ref_length'].max().reindex(all_refs_ordered).fillna(0)
    chr_offsets = chr_lengths.cumsum().shift(1).fillna(0)

    def get_ref_loc(chrom, pos):
        return chr_offsets[chrom] + pos

    coords['ref_loc_start'] = coords.apply(lambda row: get_ref_loc(row['ref'], row['ref_start']), axis=1)
    coords['ref_loc_stop'] = coords.apply(lambda row: get_ref_loc(row['ref'], row['ref_end']), axis=1)

    # Calculate alignment length for query ordering
    coords['alignment_length'] = abs(coords['query_start'] - coords['query_end'])

    # Pick longest alignment for each query to decide query ordering
    longest_alignments = coords.loc[coords.groupby('query')['alignment_length'].idxmax()]
    ordered_queries = longest_alignments.sort_values('ref_loc_start')['query'].tolist()

    # Get query lengths and calculate offsets
    query_lengths = coords.groupby('query')['query_length'].max().reindex(ordered_queries).fillna(0)
    query_offsets = query_lengths.cumsum().shift(1).fillna(0)

    def get_query_loc(query, pos):
        return query_offsets[query] + pos

    coords['query_loc_start'] = coords.apply(lambda row: get_query_loc(row['query'], row['query_start']), axis=1)
    coords['query_loc_stop'] = coords.apply(lambda row: get_query_loc(row['query'], row['query_end']), axis=1)

    # Labels (hide for small chromosomes/queries)
    total_ref_length = chr_lengths.sum()
    chr_labels = [name if length >= 0.02 * total_ref_length else "" for name, length in chr_lengths.items()]
    chr_breaks = chr_lengths.cumsum().tolist()

    total_query_length = query_lengths.sum()
    query_labels = [name if length >= 0.02 * total_query_length else "" for name, length in query_lengths.items()]
    query_breaks = query_lengths.cumsum().tolist()

    # Plotting
    plt.figure(figsize=(10, 10))
    
    colors = {"unique": "black", "repetitive": "red"}
    
    for tag in ["unique", "repetitive"]:
        df = coords[coords['tag'] == tag]
        if not df.empty:
            for _, row in df.iterrows():
                plt.plot([row['ref_loc_start'], row['ref_loc_stop']], 
                         [row['query_loc_start'], row['query_loc_stop']], 
                         color=colors[tag], linewidth=1.5, solid_capstyle='butt')

    plt.title(plot_title, fontsize=16)
    plt.xlabel("Reference", fontsize=14)
    plt.ylabel("Query", fontsize=14)

    plt.xticks(chr_breaks, chr_labels, rotation=90, fontsize=8)
    plt.yticks(query_breaks, query_labels, fontsize=8)

    plt.xlim(0, total_ref_length)
    plt.ylim(0, total_query_length)

    plt.grid(True, linestyle='-', linewidth=0.1, color='black')
    
    # Custom legend
    from matplotlib.lines import Line2D
    legend_elements = [Line2D([0], [0], color='black', lw=2, label='unique'),
                       Line2D([0], [0], color='red', lw=2, label='repetitive')]
    plt.legend(handles=legend_elements, title="Filter")

    plt.tight_layout()
    plt.savefig(plot_output_filename + ".png", dpi=200)
    plt.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: Assemblytics_dotplot.py prefix")
        sys.exit(1)
    run(sys.argv[1])
