#!/usr/bin/env python3

import sys
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

def comma_format(num):
    return "{:,}".format(int(abs(num)))

def run(output_prefix, abs_min_var, abs_max_var):
    filename = output_prefix + ".Assemblytics_structural_variants.bed"
    if not os.path.exists(filename):
        print(f"File {filename} not found.")
        return

    try:
        bed = pd.read_csv(filename, sep="\t")
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return

    if bed.empty:
        print("No variants found in BED file.")
        return

    # Rename columns to match R script expectations
    expected_cols = ["chrom", "start", "stop", "name", "size", "strand", "type", "ref_dist", "query_dist", "contig_position", "method_found"]
    bed.columns = expected_cols[:len(bed.columns)]

    # Revalue types
    type_map = {
        "Repeat_expansion": "Repeat expansion",
        "Repeat_contraction": "Repeat contraction",
        "Tandem_expansion": "Tandem expansion",
        "Tandem_contraction": "Tandem contraction"
    }
    bed['type'] = bed['type'].replace(type_map)

    types_allowed = ["Insertion", "Deletion", "Repeat expansion", "Repeat contraction", "Tandem expansion", "Tandem contraction"]
    
    # Filter for allowed types and set as categorical for consistent ordering
    bed = bed[bed['type'].isin(types_allowed)]
    bed['type'] = pd.Categorical(bed['type'], categories=types_allowed, ordered=True)

    # Color palette (Set1 from RColorBrewer: [1,2,3,4,5,7,8])
    # Set1 hex colors: #E41A1C, #377EB8, #4DAF4A, #984EA3, #FF7F00, #A65628
    # R big_palette<-brewer.pal(9,"Set1")[c(1,2,3,4,5,7)] was actually using 7th which is pink.
    # User said Set1[8] in python instead of 7 for brown.
    # Set1 colors: 1:red, 2:blue, 3:green, 4:purple, 5:orange, 6:yellow, 7:brown, 8:pink, 9:grey
    # Actually brewer.pal(9, "Set1") is:
    # 1: #E41A1C (red)
    # 2: #377EB8 (blue)
    # 3: #4DAF4A (green)
    # 4: #984EA3 (purple)
    # 5: #FF7F00 (orange)
    # 6: #FFFF33 (yellow)
    # 7: #A65628 (brown)
    # 8: #F781BF (pink)
    # 9: #999999 (grey)
    # The user says Set1[8] for brown. In R indexing starts at 1.
    # Wait, R brewer.pal(9, "Set1")[7] is brown (#A65628).
    # If the user says R is 1-indexed and they want Set1[8] in python... maybe they meant the 8th color in Set1 is brown?
    # Actually in Set1, 7 is brown and 8 is pink.
    # If the previous code used pink (#F781BF) and the user wants brown, brown is #A65628.
    big_palette = ["#E41A1C", "#377EB8", "#4DAF4A", "#984EA3", "#FF7F00", "#A65628"]

    # Prep data for log-scaled plot
    alt = bed.copy()
    contraction_types = ["Deletion", "Repeat contraction", "Tandem contraction"]
    alt.loc[alt['type'].isin(contraction_types), 'size'] = -1 * alt.loc[alt['type'].isin(contraction_types), 'size']

    alt['Type'] = "None"
    alt.loc[alt['type'].isin(["Insertion", "Deletion"]), 'Type'] = "Indel"
    alt.loc[alt['type'].isin(["Tandem expansion", "Tandem contraction"]), 'Type'] = "Tandem"
    alt.loc[alt['type'].isin(["Repeat expansion", "Repeat contraction"]), 'Type'] = "Repeat"
    # User requested order: Indel, Repeat, Tandem
    alt['Type'] = pd.Categorical(alt['Type'], categories=["Indel", "Repeat", "Tandem"], ordered=True)

    # Size cutoffs
    var_size_cutoffs = sorted(list(set([abs_min_var, 10, 50, 500, abs_max_var])))
    var_size_cutoffs = [x for x in var_size_cutoffs if x >= abs_min_var and x <= abs_max_var]

    var_type_filename = "all_variants"

    for i in range(len(var_size_cutoffs) - 1):
        min_var = var_size_cutoffs[i]
        max_var = var_size_cutoffs[i+1]
        
        if min_var < abs_max_var and max_var > abs_min_var:
            filtered_bed = bed[(bed['size'] >= min_var) & (bed['size'] <= max_var)]
            
            if not filtered_bed.empty:
                binwidth = max(1, (max_var - min_var) / 100)
                bins = np.arange(min_var, max_var + binwidth, binwidth)
                
                # Calculate global max for y-axis synchronization
                max_counts = []
                for t in types_allowed:
                    data = filtered_bed[filtered_bed['type'] == t]['size']
                    if not data.empty:
                        counts, _ = np.histogram(data, bins=bins)
                        max_counts.append(max(counts))
                global_max = max(max_counts) if max_counts else 10
                
                fig, axes = plt.subplots(nrows=len(types_allowed), ncols=1, figsize=(8, 10), sharex=True)
                fig.suptitle(f"Variants {comma_format(min_var)} to {comma_format(max_var)} bp", fontsize=16)
                
                for j, t in enumerate(types_allowed):
                    ax = axes[j]
                    data = filtered_bed[filtered_bed['type'] == t]['size']
                    ax.hist(data, bins=bins, color=big_palette[j], label=t)
                    ax.set_ylabel("Count", fontsize=8)
                    ax.tick_params(axis='both', which='major', labelsize=8)
                    ax.set_ylim(0, global_max * 1.1) # Add 10% padding
                    
                    # Remove right and top spines
                    ax.spines['right'].set_visible(False)
                    ax.spines['top'].set_visible(False)
                    
                    # Add type label inside the plot, moved up to avoid data
                    ax.text(0.98, 0.85, t, transform=ax.transAxes, horizontalalignment='right', verticalalignment='top', fontsize=10, fontweight='bold')

                plt.xlabel("Variant size", fontsize=12)
                plt.tight_layout(rect=[0, 0.03, 1, 0.95])
                
                for fmt in ['png', 'pdf']:
                    plt.savefig(f"{output_prefix}.Assemblytics.size_distributions.{var_type_filename}.{min_var}-{max_var}.{fmt}", dpi=200)
                plt.close()
            else:
                print(f"No variants in plot: min_var={min_var}, max_var={max_var}")

    # Log-scaled plot
    fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(10, 8), sharex=True)
    fig.suptitle(f"Variants {comma_format(abs_min_var)} to {comma_format(abs_max_var)} bp", fontsize=16)
    
    # User requested order: Indel, Repeat, Tandem
    categories_ordered = ["Indel", "Repeat", "Tandem"]
    types_by_category = {
        "Indel": ["Insertion", "Deletion"],
        "Repeat": ["Repeat expansion", "Repeat contraction"],
        "Tandem": ["Tandem expansion", "Tandem contraction"]
    }
    
    binwidth = (2 * abs_max_var) / 100
    bins = np.arange(-abs_max_var, abs_max_var + binwidth, binwidth)
    
    # Calculate global max for y-axis synchronization in log scale
    max_counts_log = []
    for category in categories_ordered:
        cat_data = alt[alt['Type'] == category]
        if not cat_data.empty:
            # We want to show counts + 1 to make small counts visible on log scale
            counts, _ = np.histogram(cat_data['size'], bins=bins)
            max_counts_log.append(max(counts) + 1)
    global_max_log = max(max_counts_log) if max_counts_log else 100

    for i, category in enumerate(categories_ordered):
        ax = axes[i]
        for t in types_by_category[category]:
            color_idx = types_allowed.index(t)
            data = alt[alt['type'] == t]['size']
            if not data.empty:
                # Use np.histogram and plt.bar to manually implement count + 1 for log scale
                counts, bin_edges = np.histogram(data, bins=bins)
                # To match R's log(count + 1), we plot bars of height counts + 1
                # But we need to handle the bottom of the log scale.
                # Actually, a better way to match R exactly is to plot counts + 1 and set ylim bottom to 1.
                bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
                ax.bar(bin_centers, counts + 1, width=binwidth, color=big_palette[color_idx], label=t, alpha=0.7)
        
        ax.set_yscale('log')
        ax.set_ylabel("Log(count + 1)", fontsize=10)
        ax.tick_params(axis='both', which='major', labelsize=8)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.set_ylim(1, global_max_log * 1.5)
        
        # Add category label
        ax.text(0.02, 0.85, category, transform=ax.transAxes, horizontalalignment='left', fontsize=12, fontweight='bold')
        ax.legend(loc='upper right', fontsize=8)

    plt.xlabel("Variant size", fontsize=12)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    for fmt in ['png', 'pdf']:
        plt.savefig(f"{output_prefix}.Assemblytics.size_distributions.{var_type_filename}.log_all_sizes.{fmt}", dpi=200)
    plt.close()

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: Assemblytics_variant_charts.py output_prefix abs_min_var abs_max_var")
        sys.exit(1)
    
    output_prefix = sys.argv[1]
    abs_min_var = int(sys.argv[2])
    abs_max_var = int(sys.argv[3])
    run(output_prefix, abs_min_var, abs_max_var)
