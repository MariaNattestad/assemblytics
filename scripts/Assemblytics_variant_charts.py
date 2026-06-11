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

    # Color palette (Set1 from RColorBrewer: [1,2,3,4,5,7])
    # Set1 hex colors: #E41A1C, #377EB8, #4DAF4A, #984EA3, #FF7F00, #A65628
    big_palette = ["#E41A1C", "#377EB8", "#4DAF4A", "#984EA3", "#FF7F00", "#F781BF"] # pink instead of brown for last one to match Set1[7]

    # Prep data for log-scaled plot
    alt = bed.copy()
    contraction_types = ["Deletion", "Repeat contraction", "Tandem contraction"]
    alt.loc[alt['type'].isin(contraction_types), 'size'] = -1 * alt.loc[alt['type'].isin(contraction_types), 'size']

    alt['Type'] = "None"
    alt.loc[alt['type'].isin(["Insertion", "Deletion"]), 'Type'] = "Indel"
    alt.loc[alt['type'].isin(["Tandem expansion", "Tandem contraction"]), 'Type'] = "Tandem"
    alt.loc[alt['type'].isin(["Repeat expansion", "Repeat contraction"]), 'Type'] = "Repeat"
    alt['Type'] = pd.Categorical(alt['Type'], categories=["Indel", "Tandem", "Repeat"], ordered=True)

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
                binwidth = max(1, max_var / 100)
                bins = np.arange(min_var, max_var + binwidth, binwidth)
                
                fig, axes = plt.subplots(nrows=len(types_allowed), ncols=1, figsize=(8, 10), sharex=True)
                fig.suptitle(f"Variants {comma_format(min_var)} to {comma_format(max_var)} bp", fontsize=16)
                
                for j, t in enumerate(types_allowed):
                    ax = axes[j]
                    data = filtered_bed[filtered_bed['type'] == t]['size']
                    ax.hist(data, bins=bins, color=big_palette[j], label=t)
                    ax.set_ylabel("Count", fontsize=8)
                    ax.tick_params(axis='both', which='major', labelsize=8)
                    # Remove right and top spines
                    ax.spines['right'].set_visible(False)
                    ax.spines['top'].set_visible(False)
                    
                    # Add type label inside the plot
                    ax.text(0.95, 0.8, t, transform=ax.transAxes, horizontalalignment='right', fontsize=10, fontweight='bold')

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
    
    types_by_category = {
        "Indel": ["Insertion", "Deletion"],
        "Tandem": ["Tandem expansion", "Tandem contraction"],
        "Repeat": ["Repeat expansion", "Repeat contraction"]
    }
    
    binwidth = abs_max_var / 100
    bins = np.arange(-abs_max_var, abs_max_var + binwidth, binwidth)
    
    for i, category in enumerate(["Indel", "Tandem", "Repeat"]):
        ax = axes[i]
        for t in types_by_category[category]:
            color_idx = types_allowed.index(t)
            data = alt[alt['type'] == t]['size']
            if not data.empty:
                ax.hist(data, bins=bins, color=big_palette[color_idx], label=t, alpha=0.7)
        
        ax.set_yscale('log')
        ax.set_ylabel("Log(count + 1)", fontsize=10)
        ax.tick_params(axis='both', which='major', labelsize=8)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.set_ylim(bottom=1) # count + 1 starting at 1
        
        # Add category label
        ax.text(0.02, 0.8, category, transform=ax.transAxes, horizontalalignment='left', fontsize=12, fontweight='bold')
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
