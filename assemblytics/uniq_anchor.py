#!/usr/bin/env python3

import argparse
import gzip
import os
import time
import numpy as np
import operator


def scrub(string):
    return string.replace(",","_").replace("!","_").replace("~","_").replace("#","_")


def run(args):
    filename = args.delta
    unique_length = args.unique_length
    output_dir = args.out
    keep_small_uniques = args.keep_small_uniques
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    # if keep_small_uniques:
    #     print("Keeping fully unique alignments even if they are below the unique anchor length of", unique_length, "bp")
    # else:
    #     print("Discarding all alignments below the unique anchor length of", unique_length, "bp")
    #     print("Use --keep-small-uniques to keep all the fully unique alignments even below this length")
    # if unique_length == 10000:
    #     print("Use --unique-length X to set the unique anchor length requirement. Default is 10000, such that each alignment must have at least 10000 bp from the query that are not included in any other alignments.")

    try:
        f = gzip.open(filename, 'rt')
        header1 = f.readline().strip()
        # Detected gzipped delta file.
    except:
        f = open(filename, 'r')
        header1 = f.readline().strip()
        # Detected uncompressed delta file.
   
    # Skip the second line
    f.readline()

    linecounter = 0

    current_query_name = ""
    current_header = ""

    lines_by_query = {}
    header_lines_by_query = {}

    before = time.time()
    last = before

    existing_query_names = set()

    for line in f:
        if line[0]==">":
            fields = line.strip().split()
            current_query_name = fields[1]
            current_header = line.strip()
            if current_query_name not in existing_query_names:
                lines_by_query[current_query_name] = []
                header_lines_by_query[current_query_name] = []
                existing_query_names.add(current_query_name)
        else:
            fields = line.strip().split()
            if len(fields) > 4:
                # sometimes start and end are the other way around, but for this they need to be in order
                query_min = min([int(fields[2]),int(fields[3])])
                query_max = max([int(fields[2]),int(fields[3])])

                lines_by_query[current_query_name].append((query_min,query_max))
                header_lines_by_query[current_query_name].append(current_header)

    f.close()
    

    before = time.time()
    alignments_to_keep = {}
    num_queries = len(lines_by_query)
    
    num_query_step_to_report = int(num_queries/100)
    if num_queries < 100:
        num_query_step_to_report = int(num_queries/10)
    if num_queries < 10:
        num_query_step_to_report = 1

    query_counter = 0

    for query in lines_by_query:
        alignments_to_keep[query] = summarize_planesweep(lines_by_query[query], unique_length_required = unique_length,keep_small_uniques=keep_small_uniques)

        query_counter += 1
    before = time.time()

    fout = gzip.open(os.path.join(output_dir, "assemblytics_unique_length_filtered_l%d.delta.gz" % (unique_length)),'wt')
    
    try:
        f = gzip.open(filename, 'rt')
        header1 = f.readline()
        # Detected gzipped delta file.
    except:
        f = open(filename, 'r')
        header1 = f.readline()
        # Detected uncompressed delta file.

    fout.write(header1)
    fout.write(f.readline())
    
    linecounter = 0

    # For filtered delta file:
    list_of_alignments_to_keep = []
    alignment_counter = {}
    keep_printing = False

    # For coords:
    current_query_name = ""
    current_query_position = 0
    fcoords_out_tab = open(os.path.join(output_dir, "assemblytics_coords.tab"),'w')
    fcoords_out_csv = open(os.path.join(output_dir, "assemblytics_coords.csv"),'w')
    fcoords_out_csv.write("ref_start,ref_end,query_start,query_end,ref_length,query_length,ref,query,tag\n")


    # For basic assembly stats:
    ref_sequences = set()
    query_sequences = set()
    ref_lengths = []
    query_lengths = []

    # For dot index (returned to caller):
    reference_lengths_for_dot = []
    fields_by_query_for_dot = {}
    seen_ref_names_for_dot = set()

    # For genome length files (only sequences with at least one unique alignment,
    # matching what ends up in coords.tab)
    unique_ref_entries = {}
    unique_query_entries = {}

    f_stats_out = open(os.path.join(output_dir, "assemblytics_assembly_stats.txt"),"w")

    for line in f:
        linecounter += 1
        if line[0]==">":
            fields = line.strip().split()
            
            # For delta file output:
            query = fields[1]
            list_of_alignments_to_keep = alignments_to_keep[query]

            header_needed = False
            for index in list_of_alignments_to_keep:
                if line.strip() == header_lines_by_query[query][index]:
                    header_needed = True
            if header_needed == True:
                fout.write(line) # if we have any alignments under this header, print the header
            alignment_counter[query] = alignment_counter.get(query,0)

            # For coords:
            current_reference_name = fields[0][1:]
            current_query_name = fields[1]

            current_reference_size = int(fields[2])
            current_query_size = int(fields[3])

            # For dot index:
            scrubbed_ref = scrub(current_reference_name)
            scrubbed_query = scrub(current_query_name)
            if scrubbed_ref not in seen_ref_names_for_dot:
                seen_ref_names_for_dot.add(scrubbed_ref)
                reference_lengths_for_dot.append((scrubbed_ref, current_reference_size))

            # For basic assembly stats:
            if not current_reference_name in ref_sequences:
                ref_lengths.append(current_reference_size)
                ref_sequences.add(current_reference_name)
            if not current_query_name in query_sequences:
                query_lengths.append(current_query_size)
                query_sequences.add(current_query_name)

        else:
            fields = line.strip().split()
            if len(fields) > 4:
                # For coords:
                ref_start = int(fields[0])
                ref_end = int(fields[1])
                query_start = int(fields[2])
                query_end = int(fields[3])
                csv_tag = "repetitive"
                if alignment_counter[query] in list_of_alignments_to_keep:
                    fout.write(line)
                    fcoords_out_tab.write("\t".join(map(str,[ref_start,ref_end,query_start, query_end,current_reference_size,current_query_size,current_reference_name,current_query_name])) + "\n")
                    unique_ref_entries[current_reference_name] = current_reference_size
                    unique_query_entries[current_query_name] = current_query_size
                    csv_tag = "unique"
                    keep_printing = True
                else:
                    keep_printing = False
                fcoords_out_csv.write(",".join(map(str,[ref_start,ref_end,query_start, query_end,current_reference_size,current_query_size,current_reference_name.replace(",","_"),current_query_name.replace(",","_"),csv_tag])) + "\n")
                fields_by_query_for_dot.setdefault(scrubbed_query, []).append(
                    [str(ref_start), str(ref_end), str(query_start), str(query_end),
                     str(current_reference_size), str(current_query_size),
                     scrubbed_ref, scrubbed_query, csv_tag]
                )
                alignment_counter[query] = alignment_counter[query] + 1

            elif keep_printing == True:
                fout.write(line)

    fcoords_out_tab.close()
    fcoords_out_csv.close()

    with open(os.path.join(output_dir, "assemblytics_ref.genome"), "w") as ref_genome_out:
        for name, length in sorted(unique_ref_entries.items(), key=lambda item: item[1], reverse=True):
            ref_genome_out.write("%s\t%d\n" % (name, length))

    with open(os.path.join(output_dir, "assemblytics_query.genome"), "w") as query_genome_out:
        for name, length in sorted(unique_query_entries.items(), key=lambda item: item[1], reverse=True):
            query_genome_out.write("%s\t%d\n" % (name, length))

    print("Reading file and recording all the entries we decided to keep: %d seconds for %d total lines in file" % (time.time()-before,linecounter))

    ref_lengths.sort()
    query_lengths.sort()

    # Assembly statistics
    ref_lengths = np.array(ref_lengths)
    query_lengths = np.array(query_lengths)

    f_stats_out.write("Reference: %s\n" % (header1.split()[0].split("/")[-1]))
    f_stats_out.write( "Number of sequences: %s\n" % intWithCommas(len(ref_lengths)))
    f_stats_out.write( "Total sequence length: %s\n" %  gig_meg(sum(ref_lengths)))
    f_stats_out.write( "Mean: %s\n" % gig_meg(np.mean(ref_lengths)))
    f_stats_out.write( "Min: %s\n" % gig_meg(np.min(ref_lengths)))
    f_stats_out.write( "Max: %s\n" % gig_meg(np.max(ref_lengths)))
    f_stats_out.write( "N50: %s\n" % gig_meg(N50(ref_lengths)))
    f_stats_out.write( "\n\n")
    f_stats_out.write( "Query: %s\n" % header1.split()[1].split("/")[-1])
    f_stats_out.write( "Number of sequences: %s\n" % intWithCommas(len(query_lengths)))
    f_stats_out.write( "Total sequence length: %s\n" % gig_meg(sum(query_lengths)))
    f_stats_out.write( "Mean: %s\n" % gig_meg(np.mean(query_lengths)))
    f_stats_out.write( "Min: %s\n" % gig_meg(np.min(query_lengths)))
    f_stats_out.write( "Max: %s\n" % gig_meg(np.max(query_lengths)))
    f_stats_out.write( "N50: %s\n" % gig_meg(N50(query_lengths)))


    f.close()
    fout.close()
    f_stats_out.close()

    return reference_lengths_for_dot, fields_by_query_for_dot


def N50(sorted_list):
    # List should be sorted as increasing

    # We flip the list around here so we start with the largest element
    cumsum = 0
    for length in sorted_list[::-1]:
        cumsum += length
        if cumsum >= sum(sorted_list)/2:
            return length


def gig_meg(number,digits = 2):
    gig = 1000000000.
    meg = 1000000.
    kil = 1000.

    if number > gig:
        return str(round(number/gig,digits)) + " Gbp"
    elif number > meg:
        return str(round(number/meg,digits)) + " Mbp"
    elif number > kil:
        return str(round(number/kil,digits)) + " Kbp"
    else:
        return str(number) + " bp"

def intWithCommas(x):
    if type(x) != int:
        raise TypeError("Parameter must be an integer.")
    if x < 0:
        return '-' + intWithCommas(-x)
    result = ''
    while x >= 1000:
        x, r = divmod(x, 1000)
        result = ",%03d%s" % (r, result)
    return "%d%s" % (x, result)


def summarize_planesweep(lines,unique_length_required, keep_small_uniques=False):

    alignments_to_keep = []

    # If no alignments:
    if len(lines)==0:
        return []

    # If only one alignment:
    if len(lines) == 1:
        if keep_small_uniques == True or abs(lines[0][1] - lines[0][0]) >= unique_length_required:
            return [0]
        else:
            return []

    starts_and_stops = []
    for query_min,query_max in lines:
        starts_and_stops.append((query_min,"start"))
        starts_and_stops.append((query_max,"stop"))


    sorted_starts_and_stops = sorted(starts_and_stops,key=operator.itemgetter(0))

    current_coverage = 0
    last_position = -1
    sorted_unique_intervals_left = []
    sorted_unique_intervals_right = []
    for pos,change in sorted_starts_and_stops:
        if current_coverage == 1:
            sorted_unique_intervals_left.append(last_position)
            sorted_unique_intervals_right.append(pos)

        if change == "start":
            current_coverage += 1
        else:
            current_coverage -= 1
        last_position = pos


    linecounter = 0
    for query_min,query_max in lines:

        i = binary_search(query_min,sorted_unique_intervals_left,0,len(sorted_unique_intervals_left))

        exact_match = False
        if sorted_unique_intervals_left[i] == query_min and sorted_unique_intervals_right[i] == query_max:
            exact_match = True
        sum_uniq = 0
        while i < len(sorted_unique_intervals_left) and sorted_unique_intervals_left[i] >= query_min and sorted_unique_intervals_right[i] <= query_max:
            sum_uniq += sorted_unique_intervals_right[i] - sorted_unique_intervals_left[i]
            i += 1

        if sum_uniq >= unique_length_required:
            alignments_to_keep.append(linecounter)
        elif keep_small_uniques == True and exact_match == True:
            alignments_to_keep.append(linecounter)

        linecounter += 1

    return alignments_to_keep


def binary_search(query, numbers, left, right):
    #  Returns index of the matching element or the first element to the right
    
    if left >= right:
        return right
    mid = int((right+left)/2)
    

    if query == numbers[mid]:
        return mid
    elif query < numbers[mid]:
        return binary_search(query,numbers,left,mid)
    else: # if query > numbers[mid]:
        return binary_search(query,numbers,mid+1,right)



def main():
    parser=argparse.ArgumentParser(description="Filters alignments in delta file based on whether each alignment has a unique sequence anchoring it")
    parser.add_argument("--delta",help="delta file" ,dest="delta", type=str, required=True)
    parser.add_argument("--out",help="output directory for assemblytics_* files (default: current directory)" ,dest="out", type=str, default=".")
    parser.add_argument("--unique-length",help="The total length of unique sequence an alignment must have on the query side to be retained. Default: 10000" ,dest="unique_length",type=int, default=10000)
    parser.add_argument("--keep-small-uniques",help="Keep small aligments (below the unique anchor length) if they are completely unique without any part of the alignment mapping multiple places" ,dest="keep_small_uniques",action="store_true")
    parser.set_defaults(func=run)
    args=parser.parse_args()
    args.func(args)

if __name__=="__main__":
    main()
