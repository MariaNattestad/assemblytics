#! /usr/bin/env python

# Author: Maria Nattestad
# Email: maria.nattestad@gmail.com

# This script prepares alignment coordinates for visualization in Dot


import argparse
import numpy as np
import re


def scrub(string):
	return string.replace(",","_").replace("!","_").replace("~","_").replace("#", "_")


def natural_key(string_):
	"""See http://www.codinghorror.com/blog/archives/001018.html"""
	return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string_)]


def index_for_dot(reference_lengths, fields_by_query, output_prefix, max_overview_alignments):

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
	unique_references_by_query = {} # for index, only unique alignments
	all_references_by_query = {} # for index, including repetitive alignments
	relative_ref_position_by_query = [] # for ordering


	ordered_tags = ["unique", "repetitive"]


	f_out_coords = open(output_prefix + ".coords", 'w')
	f_out_coords.write("ref_start,ref_end,query_start,query_end,ref\n")

	query_byte_positions = {}
	query_lengths = {}

	all_alignments = []
	last_query = ""

	for query_name in fields_by_query:

		lines = fields_by_query[query_name]
		sum_forward = 0
		sum_reverse = 0
		ref_position_scores = []
		unique_references_by_query[query_name] = set()
		all_references_by_query[query_name] = set()

		for fields in lines:
			tag = fields[8]

			query_name = fields[7]
			query_lengths[query_name] = int(fields[5])

			all_references_by_query[query_name].add(fields[6])
			# Only use unique alignments to decide contig orientation
			if tag == "unique":
				query_stop = int(fields[3])
				query_start = int(fields[2])
				ref_start = int(fields[0])
				ref_stop = int(fields[1])
				alignment_length = abs(int(fields[3])-int(fields[2]))
				ref = fields[6]

				# for index:
				unique_references_by_query[query_name].add(ref)
				queries_by_reference[ref].add(query_name)

				# for ordering:
				ref_position_scores.append(ref_chrom_offsets[ref] + (ref_start+ref_stop)/2)

				# for orientation:
				if query_stop < query_start:
					sum_reverse += alignment_length
				else:
					sum_forward += alignment_length

		# orientation:
		flip = sum_reverse > sum_forward
		flip_by_query[query_name] = "-" if flip else "+"


		for tag in ordered_tags:
			query_byte_positions[(last_query, "end")] = f_out_coords.tell()
			query_byte_positions[(query_name, tag)] = f_out_coords.tell()
			f_out_coords.write("!" + query_name + "!" + tag +"\n")

			for fields in lines:
				if fields[8] == tag:
					if flip:
						fields[2] = int(fields[5]) - int(fields[2])
						fields[3] = int(fields[5]) - int(fields[3])

					output_fields = [fields[0], fields[1], fields[2], fields[3], fields[6]]
					f_out_coords.write(",".join([str(i) for i in output_fields]) + "\n")

					# For alignment overview:
					alignment_length = abs(int(fields[3])-int(fields[2]))
					all_alignments.append(([fields[0], fields[1], fields[2], fields[3], fields[6], fields[7], fields[8]], alignment_length))

		# ordering
		if len(ref_position_scores) > 0:
			relative_ref_position_by_query.append((query_name,np.median(ref_position_scores)))
		else:
			relative_ref_position_by_query.append((query_name,0))

		last_query = query_name


	query_byte_positions[(last_query, "end")] = f_out_coords.tell()

	relative_ref_position_by_query.sort(key=lambda x: x[1])

	f_out_index = open(output_prefix + ".coords.idx", 'w')

	f_out_index.write("#ref\n")
	f_out_index.write("ref,ref_length,matching_queries\n")
	# reference_lengths is sorted by the reference chromosome name
	for ref,ref_length in reference_lengths:
		f_out_index.write("%s,%d,%s\n" % (ref,ref_length,"~".join(queries_by_reference[ref])))

	f_out_index.write("#query\n")
	f_out_index.write("query,query_length,orientation,bytePosition_unique,bytePosition_repetitive,bytePosition_end,unique_matching_refs,matching_refs\n")
	# relative_ref_position_by_query is sorted by rel_pos
	for query,_ in relative_ref_position_by_query:
		f_out_index.write("%s,%d,%s,%d,%d,%d,%s,%s\n" % (query, query_lengths[query], flip_by_query[query], query_byte_positions[(query,"unique")], query_byte_positions[(query,"repetitive")] - query_byte_positions[(query,"unique")], query_byte_positions[(query,"end")] - query_byte_positions[(query,"repetitive")], "~".join(unique_references_by_query[query]), "~".join(all_references_by_query[query])))

	f_out_index.write("#overview\n")
	f_out_index.write("ref_start,ref_end,query_start,query_end,ref,query,tag\n")

	num_overview_alignments = min(max_overview_alignments,len(all_alignments))
	if num_overview_alignments < len(all_alignments):
		print("Included the longest " + str(max_overview_alignments) + " alignments in the index under #overview (change this with the --overview parameter), out of a total of " + str(len(all_alignments)) + " alignments.")

	all_alignments.sort(key=lambda x: -x[1])
	overview_alignments = all_alignments[0:num_overview_alignments]
	for tup in overview_alignments:
		f_out_index.write(",".join([str(i) for i in tup[0]]) + "\n")

	f_out_index.close()


def main():
	parser=argparse.ArgumentParser(description="Take a delta file, apply Assemblytics unique anchor filtering, and prepare coordinates input files for Dot")
	parser.add_argument("--delta",help="delta file" ,dest="delta", type=str, required=True)
	parser.add_argument("--out",help="output file prefix" ,dest="out", type=str, default="output")
	parser.add_argument("--unique-length",help="The total length of unique sequence an alignment must have on the query side to be retained. Default: 10000" ,dest="unique_length",type=int, default=10000)
	parser.add_argument("--overview",help="The number of alignments to include in the coords.idx output file. Default: 1000" ,dest="overview",type=int, default=1000)
	args=parser.parse_args()

	import os
	from .uniq_anchor import run as run_uniq_anchor
	out_dir = os.path.dirname(args.out) or "."
	reference_lengths, fields_by_query = run_uniq_anchor(
		argparse.Namespace(delta=args.delta, out=out_dir, unique_length=args.unique_length, keep_small_uniques=True)
	)
	index_for_dot(reference_lengths, fields_by_query, args.out, args.overview)


if __name__=="__main__":
	main()
