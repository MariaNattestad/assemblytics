#!/usr/bin/env python3

import argparse
import numpy as np
import re


def run(args):

    coords = args.coords
    output_prefix = args.out
    
    f = open(coords)
    f.readline() # ignore header

    fields_by_query = {}
    existing_query_names = set()
    existing_reference_names = set()
    reference_lengths = []
    query_lengths = {}
    for line in f:
        fields = line.strip().split(",")
        query_name = fields[7]
        query_lengths[query_name] = int(fields[5])
        if not query_name in existing_query_names:
            fields_by_query[query_name] = []
            existing_query_names.add(query_name)
        fields_by_query[query_name].append(fields)

        ref_name = fields[6]
        ref_length = int(fields[4])
        if not ref_name in existing_reference_names:
            existing_reference_names.add(ref_name)
            reference_lengths.append((ref_name,ref_length))

    f.close()


    #  Find the order of the reference chromosomes
    reference_lengths.sort(key=lambda x: natural_key(x[0]))
    
    #  Find the cumulative sums
    cumulative_sum = 0
    ref_chrom_offsets = {}
    queries_by_reference = {}
    for ref,ref_length in reference_lengths:
        ref_chrom_offsets[ref] = cumulative_sum
        cumulative_sum += ref_length
        queries_by_reference[ref] = set()

    #  Calculate relative positions of each alignment in this cumulative length, and take the median of these for each query, then sort the queries by those scores
    flip_by_query = {}
    references_by_query = {} # for index
    relative_ref_position_by_query = [] # for ordering


    for query_name in fields_by_query:
        lines = fields_by_query[query_name]
        sum_forward = 0
        sum_reverse = 0
        amount_of_reference = {}
        ref_position_scores = []
        references_by_query[query_name] = set()
        for ref,ref_length in reference_lengths:
            amount_of_reference[ref] = 0
        for fields in lines:
            tag = fields[8]
            if tag == "unique":
                query_stop = int(fields[3])
                query_start = int(fields[2])
                ref_start = int(fields[0])
                ref_stop = int(fields[1])
                alignment_length = abs(int(fields[3])-int(fields[2]))
                ref = fields[6]
                
                # for index:
                references_by_query[query_name].add(ref)
                queries_by_reference[ref].add(query_name)
                # amount_of_reference[ref] += alignment_length 

                # for ordering:
                ref_position_scores.append(ref_chrom_offsets[ref] + (ref_start+ref_stop)/2)

                # for orientation:
                if query_stop < query_start:
                    sum_reverse += alignment_length
                else:
                    sum_forward += alignment_length
        # orientation:
        flip_by_query[query_name] = sum_reverse > sum_forward

        # ordering
        if len(ref_position_scores) > 0:
            relative_ref_position_by_query.append((query_name,np.median(ref_position_scores)))
        else:
            relative_ref_position_by_query.append((query_name,0))


    relative_ref_position_by_query.sort(key=lambda x: x[1])

    fout_ref_index = open(output_prefix + ".ref.index",'w')
    fout_ref_index.write("ref,ref_length,matching_queries\n")

    # reference_lengths is sorted by the reference chromosome name
    for ref,ref_length in reference_lengths:
        fout_ref_index.write("%s,%d,%s\n" % (ref,ref_length,"~".join(queries_by_reference[ref])))
    fout_ref_index.close()

    fout_query_index = open(output_prefix + ".query.index",'w')
    fout_query_index.write("query,query_length,matching_refs\n")

    # relative_ref_position_by_query is sorted by rel_pos
    for query,rel_pos in relative_ref_position_by_query:
        fout_query_index.write("%s,%d,%s\n" % (query,query_lengths[query],"~".join(references_by_query[query])))
    fout_query_index.close()


    f = open(coords)
    fout = open(output_prefix + ".oriented_coords.csv",'w')
    header = f.readline().strip()
    fout.write(header+",alignment_length\n") # copy the header

    alignment_length_column = len(header.split(","))

    uniques = []
    repetitives = []

    for line in f:
        fields = line.strip().split(",")
        query_name = fields[7]
        if flip_by_query[query_name] == True:
            fields[2] = int(fields[5]) - int(fields[2])
            fields[3] = int(fields[5]) - int(fields[3])
            alignment_length = abs(int(fields[2]) - int(fields[1]))
        else:
            alignment_length = abs(int(fields[3]) - int(fields[2]))
        fields.append(alignment_length)
        if fields[8] == "unique":
            uniques.append(fields)
        else:
            repetitives.append(fields)
    f.close()

    uniques.sort(key=lambda x: x[alignment_length_column],reverse=True)
    repetitives.sort(key=lambda x: x[alignment_length_column],reverse=True)
    
    fout_info = open(output_prefix + ".info.csv",'w')
    fout_info.write("key,value\n")
    fout_info.write("unique alignments,%d\n" % len(uniques))
    fout_info.write("repetitive alignments,%d\n" % len(repetitives))


    for fields in uniques:
        fout.write(",".join(map(str,fields)) + "\n")

    if len(repetitives) < 100000:
        for fields in repetitives:
            fout.write(",".join(map(str,fields)) + "\n")
        fout_info.write("showing repetitive alignments,True\n")
    else:
        fout_repeats = open(output_prefix + ".oriented_coords.repetitive.csv",'w')
        fout_repeats.write(header+",alignment_length\n") # copy the header
        for fields in repetitives:
            fout_repeats.write(",".join(map(str,fields)) + "\n")
        fout_repeats.close()
        fout_info.write("showing repetitive alignments,False: Too many\n")

    fout.close()
    fout_info.close()

def natural_key(string_):
    """See http://www.codinghorror.com/blog/archives/001018.html"""
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string_)]


def main():
    parser=argparse.ArgumentParser(description="Index and orient a coordinate file for dotplots.")
    parser.add_argument("-coords",help="coords.csv file from Assemblytics_uniq_anchor.py" ,dest="coords", type=str, required=True)
    parser.add_argument("-out",help="output prefix for indices and oriented coordinates file" ,dest="out", type=str, required=True)
    parser.set_defaults(func=run)
    args=parser.parse_args()
    args.func(args)

if __name__=="__main__":
    main()