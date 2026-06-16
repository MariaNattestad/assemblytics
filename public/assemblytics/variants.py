#!/usr/bin/env python3

"""Find structural variants between and within alignments in a single pass
over the filtered delta file (the one uniq_anchor.py writes).

The filtered delta only contains kept/unique alignments, so one read of it
gives us everything that used to require two separate reads:
- the per-alignment coordinates (rstart/rend/qstart/qend/rlen/qlen/rid/qid)
  that between-alignment SV calling needs (previously re-derived from
  coords.tab),
- the gap/tick lines within each alignment that within-alignment SV calling
  scans (previously a second, separate read of this same filtered delta).
"""

import gzip
import sys

STRUCTURAL_VARIANTS_HEADER = (
    "#reference\tref_start\tref_stop\tID\tsize\tstrand\ttype\t"
    "ref_gap_size\tquery_gap_size\tquery_coordinates\tmethod"
)

NARROW_THRESHOLD = 50
MAX_QUERY_DIST = 100000
MIN_SV_ALIGN = 100


def format_position(chrom, coord1, coord2, positive):
    if positive:
        return "%s:%d-%d:+" % (chrom, coord1, coord2)
    return "%s:%d-%d:-" % (chrom, coord1, coord2)


def classify_sv(ai, aj, rid, qid, narrow_threshold, longrange, max_query_dist):
    istr = ai["str"]
    jstr = aj["str"]

    rdist = 0
    qdist = 0
    svtype = ""
    qpos = ""

    chromi = ai["rid"]
    chromj = aj["rid"]
    posi = 0
    posj = 0
    strandi = "+"
    strandj = "+"

    if ai["qrc"] == 0 and aj["qrc"] == 0:
        svtype = "FF"
        qdist = aj["qstart"] - ai["qend"]
        rdist = aj["rstart"] - ai["rend"]
        if rdist >= 0:
            rpos = format_position(rid, ai["rend"], aj["rstart"], True)
        else:
            rpos = format_position(rid, aj["rstart"], ai["rend"], False)
        if qdist >= 0:
            qpos = format_position(qid, ai["qend"], aj["qstart"], True)
        else:
            qpos = format_position(qid, aj["qstart"], ai["qend"], False)
        posi = ai["rend"]
        posj = aj["rstart"]
        strandi = "+"
        strandj = "-"
    elif ai["qrc"] == 1 and aj["qrc"] == 1:
        svtype = "RR"
        rdist = ai["rstart"] - aj["rend"]
        qdist = aj["qend"] - ai["qstart"]
        if rdist >= 0:
            rpos = format_position(rid, aj["rend"], ai["rstart"], True)
        else:
            rpos = format_position(rid, ai["rstart"], aj["rend"], False)
        if qdist >= 0:
            qpos = format_position(qid, ai["qstart"], aj["qend"], True)
        else:
            qpos = format_position(qid, aj["qend"], ai["qstart"], False)
        posi = ai["rstart"]
        posj = aj["rend"]
        strandi = "-"
        strandj = "+"
    elif ai["qrc"] == 0 and aj["qrc"] == 1:
        svtype = "FR"
        qdist = aj["qend"] - ai["qend"]
        rdist = aj["rstart"] - ai["rend"]
        if rdist >= 0:
            rpos = format_position(rid, ai["rend"], aj["rstart"], True)
        else:
            rpos = format_position(rid, aj["rstart"], ai["rend"], False)
        if qdist >= 0:
            qpos = format_position(qid, ai["qend"], aj["qend"], True)
        else:
            qpos = format_position(qid, aj["qend"], ai["qend"], False)
        posi = ai["rend"]
        posj = aj["rend"]
        strandi = "+"
        strandj = "+"
    elif ai["qrc"] == 1 and aj["qrc"] == 0:
        svtype = "RF"
        qdist = ai["qend"] - aj["qend"]
        rdist = aj["rstart"] - ai["rend"]
        if rdist >= 0:
            rpos = format_position(rid, ai["rend"], aj["rstart"], True)
        else:
            rpos = format_position(rid, aj["rstart"], ai["rend"], False)
        if qdist >= 0:
            qpos = format_position(qid, aj["qend"], ai["qend"], True)
        else:
            qpos = format_position(qid, ai["qend"], aj["qend"], False)
        posi = ai["rstart"]
        posj = aj["rstart"]
        strandi = "-"
        strandj = "-"
    else:
        print("ERROR: Unknown SV: %s %s" % (ai["qrc"], aj["qrc"]), file=sys.stderr)
        print(istr, file=sys.stderr)
        print(jstr, file=sys.stderr)
        raise SystemExit("ERROR: Unknown SV: %s %s" % (ai["qrc"], aj["qrc"]))

    abs_event_size = abs(rdist - qdist)
    typeguess = ""

    if chromi != chromj:
        typeguess = "Interchromosomal"
        rdist = 0
    else:
        if strandi == strandj:
            typeguess = "Inversion"
            abs_event_size = rdist
        elif qdist > rdist:
            if (
                rdist > -1 * narrow_threshold
                and rdist < narrow_threshold
                and qdist > -1 * narrow_threshold
            ):
                typeguess = "Insertion"
            elif rdist < 0 or qdist < 0:
                typeguess = "Tandem_expansion"
            else:
                typeguess = "Repeat_expansion"
        elif qdist < rdist:
            if (
                rdist > -1 * narrow_threshold
                and qdist > -1 * narrow_threshold
                and qdist < narrow_threshold
            ):
                typeguess = "Deletion"
            elif rdist < 0 or qdist < 0:
                typeguess = "Tandem_contraction"
            else:
                typeguess = "Repeat_contraction"
        else:
            typeguess = "None"

        if abs_event_size > longrange:
            typeguess = "Longrange"
            if abs(qdist) > max_query_dist:
                typeguess = "None"

    return {
        "chromi": chromi,
        "chromj": chromj,
        "posi": posi,
        "posj": posj,
        "strandi": strandi,
        "strandj": strandj,
        "rdist": rdist,
        "qdist": qdist,
        "qpos": qpos,
        "abs_event_size": abs_event_size,
        "typeguess": typeguess,
        "svtype": svtype,
    }


def classify_for_output(sv, minimum_event_size):
    """Returns "main", "longrange", or None (drop) for this candidate SV.

    chromosome_filter="all-chromosomes" is the only mode ever used by the
    orchestrator, so that filter is hardcoded away (it was a no-op in that
    mode anyway). Long-range/interchromosomal candidates are routed to a
    separate bucket instead of being dropped, so the caller can choose to
    keep them in their own output file.
    """
    typeguess = sv["typeguess"]
    abs_event_size = sv["abs_event_size"]

    if typeguess in ("Inversion", "None"):
        return None
    if abs_event_size < minimum_event_size:
        return None
    if typeguess in ("Interchromosomal", "Longrange"):
        return "longrange"
    return "main"


def format_bed_record(sv_id_counter, sv):
    ref_start = min(sv["posi"], sv["posj"])
    ref_stop = max(sv["posi"], sv["posj"])
    if ref_stop == ref_start:
        ref_stop = ref_start + 1

    return "\t".join(
        map(
            str,
            [
                sv["chromi"],
                ref_start,
                ref_stop,
                "Assemblytics_b_%d" % sv_id_counter,
                sv["abs_event_size"],
                "+",
                sv["typeguess"],
                sv["rdist"],
                sv["qdist"],
                sv["qpos"],
                "between_alignments",
            ],
        )
    )


def find_between_alignment_variants(alignments, minimum_event_size, maximum_event_size):
    sv_id_counter = 0
    main_lines = []
    longrange_lines = []

    for qid in sorted(alignments):
        refs = sorted(alignments[qid])
        qaligns = []
        for rid in refs:
            qaligns.extend(alignments[qid][rid])

        qaligns.sort(key=lambda alignment: alignment["qstart"])

        if len(qaligns) <= 1:
            continue

        for j in range(1, len(qaligns)):
            ai = qaligns[j - 1]
            aj = qaligns[j]
            rid = ai["rid"]

            if ai["rlen"] < MIN_SV_ALIGN or aj["rlen"] < MIN_SV_ALIGN:
                continue

            sv_id_counter += 1
            sv = classify_sv(ai, aj, rid, qid, NARROW_THRESHOLD, maximum_event_size, MAX_QUERY_DIST)

            bucket = classify_for_output(sv, minimum_event_size)
            if bucket == "main":
                main_lines.append(format_bed_record(sv_id_counter, sv))
            elif bucket == "longrange":
                longrange_lines.append(format_bed_record(sv_id_counter, sv))

    return main_lines, longrange_lines


def find_within_alignment_variants(within_variants, minimum_variant_size):
    output_lines = []
    newcounter = 1
    for line in within_variants:
        if line[4] >= minimum_variant_size:
            line[3] = "Assemblytics_w_%d" % newcounter
            output_lines.append(
                "\t".join(map(str, line[0:10])) + ":" + str(line[11]) + "-" + str(line[12]) + ":+\t" + line[10]
            )
            newcounter += 1
    return output_lines


LONGRANGE_HEADER_COMMENT = (
    "# Long-range and inter-chromosomal candidate variants: these are usually caused by "
    "misassemblies, but can also represent real translocations or other large-scale "
    "rearrangements. Inspect manually before treating them as confirmed structural variants."
)


def run(filtered_delta_path, minimum_event_size, maximum_event_size, minimum_variant_size, output_path, long_range_output_path=None):
    try:
        f = gzip.open(filtered_delta_path, 'rt')
        f.readline()  # first line: reference/query fasta paths
    except OSError:
        f = open(filtered_delta_path, 'r')
        f.readline()
    f.readline()  # second line, e.g. "NUCMER"

    alignments = {}
    within_variants = []

    current_reference_name = ""
    current_query_name = ""
    current_reference_full_length = 0
    current_query_full_length = 0
    current_reference_position = 0
    current_query_position = 0

    for line in f:
        if line[0] == ">":
            fields = line.strip().split()
            current_reference_name = fields[0][1:]
            current_query_name = fields[1]
            current_reference_full_length = int(fields[2])
            current_query_full_length = int(fields[3])
        else:
            fields = line.strip().split()
            if len(fields) > 4:
                rstart, rend, qstart, qend = int(fields[0]), int(fields[1]), int(fields[2]), int(fields[3])

                alignment = {
                    "rstart": rstart,
                    "rend": rend,
                    "qstart": qstart,
                    "qend": qend,
                    "rlen": current_reference_full_length,
                    "qlen": current_query_full_length,
                    "rid": current_reference_name,
                    "qid": current_query_name,
                    "str": line.rstrip("\n"),
                    "qidx": 0,
                    "qrc": 0 if qend > qstart else 1,
                }
                alignments.setdefault(current_query_name, {}).setdefault(current_reference_name, []).append(alignment)

                current_reference_position = min(rstart, rend)
                current_query_position = min(qstart, qend)
            else:
                tick = int(fields[0])
                if abs(tick) == 1:  # go back and edit the last entry to add 1 more to its size
                    report = within_variants[-1]
                    report[4] = report[4] + 1  # size
                    if tick > 0:  # deletion, moves in reference
                        report[2] = report[2] + 1  # reference end position
                        report[7] = report[7] + 1  # reference gap size
                        current_reference_position += 1
                    elif tick < 0:  # insertion, moves in query
                        report[8] = report[8] + 1  # query gap size
                        report[12] = report[12] + 1  # query end position
                        current_query_position += 1
                else:  # report the last one and continue
                    current_reference_position += abs(tick) - 1
                    current_query_position += abs(tick) - 1
                    if tick > 0:
                        size = 1
                        report = [
                            current_reference_name, current_reference_position, current_reference_position + size,
                            "Assemblytics_w_" + str(len(within_variants) + 1), size, "+", "Deletion", size, 0,
                            current_query_name, "within_alignment", current_query_position, current_query_position,
                        ]
                        current_reference_position += size
                        within_variants.append(report)
                    elif tick < 0:
                        size = 1
                        report = [
                            current_reference_name, current_reference_position, current_reference_position,
                            "Assemblytics_w_" + str(len(within_variants) + 1), size, "+", "Insertion", 0, size,
                            current_query_name, "within_alignment", current_query_position, current_query_position + size,
                        ]
                        current_query_position += size
                        within_variants.append(report)

    f.close()

    within_lines = find_within_alignment_variants(within_variants, minimum_variant_size)
    between_lines, longrange_lines = find_between_alignment_variants(
        alignments, minimum_event_size, maximum_event_size
    )

    with open(output_path, "w") as out:
        out.write(STRUCTURAL_VARIANTS_HEADER + "\n")
        for line in within_lines:
            out.write(line + "\n")
        for line in between_lines:
            out.write(line + "\n")

    if long_range_output_path:
        with open(long_range_output_path, "w") as out:
            out.write(LONGRANGE_HEADER_COMMENT + "\n")
            out.write(STRUCTURAL_VARIANTS_HEADER + "\n")
            for line in longrange_lines:
                out.write(line + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("Usage: variants.py filtered_delta minimum_event_size maximum_event_size minimum_variant_size output_path [long_range_output_path]")
        sys.exit(1)
    long_range_path = sys.argv[6] if len(sys.argv) > 6 else None
    run(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], long_range_path)
