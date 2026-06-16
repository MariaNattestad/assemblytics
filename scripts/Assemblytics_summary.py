#!/usr/bin/env python3

import argparse
import os
import numpy as np

def SVtable(args):
    filename = args.file
    minimum_variant_size = args.minimum_variant_size
    maximum_variant_size = args.maximum_variant_size
    simplify_types = False

    f=open(filename)
    typeList = []
    sizeList = []
    rawTypes = []
    linecounter = 0
    for line in f:
        fields = line.strip().split()
        if not fields[4].isdigit():
            continue
        svType = fields[6]
        rawTypes.append(svType)
        if simplify_types == True:
            if svType == "Insertion" or svType == "Expansion":
                typeList.append("Insertion/Expansion")
            elif svType == "Deletion" or svType == "Contraction":
                typeList.append("Deletion/Contraction")
            else:
                typeList.append(svType)
        else:
            typeList.append(svType)
        sizeList.append(int(fields[4]))
        linecounter += 1
    f.close()
    
    size_thresholds = [10,50,500,10000,50000,100000,500000,1000000]

    sizeArray = np.array(sizeList)
    typeArray = np.array(typeList)
    svTypes = ["Insertion","Deletion","Repeat_expansion","Repeat_contraction","Tandem_expansion","Tandem_contraction"]
    if simplify_types == True:
        svTypes = ["Insertion/Expansion","Deletion/Contraction"]
    overall_total = 0
    overall_total_bases = 0
    overall_total_SVs = 0
    overall_total_SV_bases = 0

    SV_size = 50

    all_SV_types = svTypes + list(set(rawTypes)-set(svTypes))

    base, _ = os.path.splitext(filename)
    f_output_csv = open(base + "_summary.csv",'w')

    if linecounter > 0:
        for svType in all_SV_types:
            sizes = sizeArray[typeArray==svType]
            overall_total += len(sizes)
            overall_total_bases += sum(sizes)
            overall_total_SVs += len(sizes[sizes>=SV_size])
            overall_total_SV_bases += sum(sizes[sizes>=SV_size])
            print(svType)
            f_output_csv.write(svType + "\n")
            
            format = "%20s%10s%15s"

            print(format % ("", "Count","Total bp"))
            f_output_csv.write("Size range,Count,Total bp\n")

            previous_size = minimum_variant_size
            for threshold in size_thresholds:
                if threshold <= minimum_variant_size or previous_size >= maximum_variant_size:
                    continue
                subset = sizes[np.logical_and(sizes>=previous_size,sizes<threshold)]; 
                print(format % ("%s-%s bp: " % (intWithCommas(previous_size),intWithCommas(threshold)), str(len(subset)), str(sum(subset))))
                f_output_csv.write("%s,%s,%s\n" % ("%s-%s bp" % (previous_size,threshold), str(len(subset)), str(sum(subset))))
                previous_size = threshold

            if previous_size < maximum_variant_size:
                subset = sizes[sizes>=previous_size];    
                print(format % ("> %s bp: " % (intWithCommas(previous_size)), str(len(subset)), str(sum(subset))))
                f_output_csv.write("%s,%s,%s\n" % ("> %s bp" % (previous_size), str(len(subset)), str(sum(subset))))

            print(format % ("Total: ",str(len(sizes)),str(sum(sizes))) + "\n")
            f_output_csv.write("%s,%s,%s\n\n" % ("Total",str(len(sizes)),str(sum(sizes))))
    else:
        print("No variants found. Plots depicting variant size distributions will also be missing.\n")

    print("Total number of all variants: %s" % (intWithCommas(overall_total)))
    f_output_csv.write("Total for all variants,%s,%s bp\n" % (overall_total,int(overall_total_bases)))
    print("Total bases affected by all variants: %s" % (gig_meg(int(overall_total_bases))))

    print("Total number of structural variants: %s" % (intWithCommas(overall_total_SVs)))
    f_output_csv.write("Total for all structural variants,%s,%s bp\n" % (overall_total_SVs,int(overall_total_SV_bases))  )
    print("Total bases affected by structural variants: %s" % (gig_meg(int(overall_total_SV_bases))))

    f_output_csv.close()

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

def main():
    parser=argparse.ArgumentParser(description='Output a summary table of variants from Assemblytics',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i',help='bed file of variants from Assemblytics',dest='file',type=str,required=True)
    parser.add_argument('-min',help='minimum variant size',dest='minimum_variant_size',type=int,required=True)
    parser.add_argument('-max',help='maximum variant size',dest='maximum_variant_size',type=int,required=True)

    args=parser.parse_args()
    SVtable(args)
    
if __name__=="__main__":
    main()











