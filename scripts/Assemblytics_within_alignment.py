#!/usr/bin/env python3

# Author: Maria Nattestad
# github.com/marianattestad/assemblytics

from __future__ import print_function

import argparse
import gzip

def run(args):
    filename = args.delta
    minimum_variant_size = args.minimum_variant_size

    try:
        f = gzip.open(filename, 'rt')
        header1 = f.readline().strip()
        print("Detected gzipped delta file. Reading...")
    except:
        f = open(filename, 'r')
        header1 = f.readline().strip()
        print("Detected uncompressed delta file. Reading...")
   
    # Ignore the first two lines for now
    print("\n")
    print("Header (2 lines):")
    print(header1)
    print(f.readline().strip())
    print("\n")

    linecounter = 0

    current_reference_name = ""
    current_reference_position = 0

    current_query_name = ""
    current_query_position = 0

    variants = []

    for line in f:
        if line[0]==">":
            fields = line.strip().split()
            current_reference_name = fields[0][1:]
            current_query_name = fields[1]
        else:
            fields = line.strip().split()
            if len(fields) > 4:
                current_reference_position = min(int(fields[0]), int(fields[1]))
                # fields[1] is the reference position at the end of the alignment
                current_query_position = min(int(fields[2]), int(fields[3]))
                # fields[3] is the query position at the end of the alignment
            else:
                tick = int(fields[0])
                if abs(tick) == 1: # then go back and edit the last entry to add 1 more to its size
                    report = variants[-1]
                    report[4] = report[4] + 1 # size
                    if tick > 0: # deletion, moves in reference
                        report[2] = report[2] + 1 # reference end position
                        report[7] = report[7] + 1 # reference gap size
                        current_reference_position += 1 # update reference position after deletion
                    elif tick < 0: # insertion, moves in query
                        report[8] = report[8] + 1 # query gap size
                        report[12] = report[12] + 1 # query end position
                        current_query_position += 1 # update query position after insertion
                else: # report the last one and continue
                    current_reference_position += abs(tick) - 1 
                    current_query_position += abs(tick) - 1 
                    if tick > 0:
                        size = 1
                        report = [current_reference_name,current_reference_position,current_reference_position+size,"Assemblytics_w_"+str(len(variants)+1),size,"+","Deletion",size,0,current_query_name,"within_alignment",current_query_position,current_query_position]
                        current_reference_position += size # update reference position after deletion
                        variants.append(report)
                    elif tick < 0:
                        size = 1
                        report = [current_reference_name,current_reference_position,current_reference_position,"Assemblytics_w_"+str(len(variants)+1),size,"+","Insertion",0,size,current_query_name,"within_alignment",current_query_position,current_query_position+size]
                        current_query_position += size # update query position after insertion
                        variants.append(report)

    f.close()

    fout = open(args.output_path, 'w')
    newcounter = 1
    for line in variants:
        if line[4] >= minimum_variant_size:
            line[3] = "Assemblytics_w_%d" % (newcounter)
            fout.write("\t".join(map(str,line[0:10])) + ":" + str(line[11]) + "-" + str(line[12]) + ":+\t" + line[10] + "\n")
            newcounter += 1
    fout.close()

def main():
    parser=argparse.ArgumentParser(description="Outputs MUMmer coordinates annotated with length of unique sequence for each alignment")
    parser.add_argument("--delta",help="delta file" ,dest="delta", type=str, required=True)
    parser.add_argument("--min",help="Minimum size (bp) of variant to include, default = 50" ,dest="minimum_variant_size",type=int, default=50)
    parser.add_argument("--output", help="Output file with variants in bed format.", dest="output_path", type=str, required=True)
    parser.set_defaults(func=run)
    args=parser.parse_args()
    args.func(args)

if __name__=="__main__":
    main()

