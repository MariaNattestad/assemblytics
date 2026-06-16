#!/usr/bin/env python3

# Originally by Mike Schatz, modified by Maria Nattestad
# Ported from Perl to Python for Assemblytics

import argparse
import sys


CHROMOSOME_FILTER_CHOICES = ("all-chromosomes", "primary-chromosomes")
LONGRANGE_FILTER_CHOICES = ("include-longrange", "exclude-longrange", "longrange-only")
OUTPUT_FILE_CHOICES = ("bed", "bedpe")

USAGE = (
    "Usage:\n"
    "between_alignments.py coords.tab minimum_event_size maximum_event_size "
    "[{0}] [{1}] [{2}]".format(
        "|".join(CHROMOSOME_FILTER_CHOICES),
        "|".join(LONGRANGE_FILTER_CHOICES),
        "|".join(OUTPUT_FILE_CHOICES),
    )
)


def load_alignments(coordsfile):
    alignments = {}
    numalignments = 0

    with open(coordsfile) as coords:
        for line in coords:
            vals = line.split()
            rid = vals[6]
            qid = vals[7]

            alignment = {
                "rstart": int(vals[0]),
                "rend": int(vals[1]),
                "qstart": int(vals[2]),
                "qend": int(vals[3]),
                "rlen": int(vals[4]),
                "qlen": int(vals[5]),
                "rid": vals[6],
                "qid": vals[7],
                "str": line.rstrip("\n"),
                "qidx": 0,
                "qrc": 0 if int(vals[3]) > int(vals[2]) else 1,
            }

            alignments.setdefault(qid, {}).setdefault(rid, []).append(alignment)
            numalignments += 1

    print("Loaded %d alignments" % numalignments, file=sys.stderr)
    return alignments


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


def passes_filters(
    sv,
    minimum_event_size,
    chromosome_filter,
    longrange_filter,
):
    typeguess = sv["typeguess"]
    abs_event_size = sv["abs_event_size"]
    chromi_length = len(sv["chromi"])
    chromj_length = len(sv["chromj"])

    if typeguess in ("Inversion", "None"):
        return False
    if abs_event_size < minimum_event_size:
        return False
    if not (
        chromosome_filter == "all-chromosomes"
        or (chromi_length < 6 and chromj_length < 6)
    ):
        return False
    if longrange_filter == "exclude-longrange" and typeguess in (
        "Interchromosomal",
        "Longrange",
    ):
        return False
    if longrange_filter == "longrange-only" and typeguess not in (
        "Interchromosomal",
        "Longrange",
    ):
        return False
    return True


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


def format_bedpe_record(sv_id_counter, sv):
    posi = sv["posi"]
    posj = sv["posj"]
    return "\t".join(
        map(
            str,
            [
                sv["chromi"],
                posi,
                posi + 1,
                sv["chromj"],
                posj,
                posj + 1,
                "Assemblytics_b_%d" % sv_id_counter,
                sv["abs_event_size"],
                sv["strandi"],
                sv["strandj"],
                sv["typeguess"],
                sv["rdist"],
                sv["qdist"],
                sv["qpos"],
                sv["abs_event_size"],
                sv["svtype"],
                "between_alignments",
            ],
        )
    )


def run(args):
    if (
        args.chromosome_filter not in CHROMOSOME_FILTER_CHOICES
        or args.longrange_filter not in LONGRANGE_FILTER_CHOICES
        or args.output_file not in OUTPUT_FILE_CHOICES
    ):
        raise SystemExit(USAGE)

    if args.longrange_filter != "exclude-longrange" and args.output_file == "bed":
        raise SystemExit("Cannot output bed while allowing long-range variants\n" + USAGE)

    narrow_threshold = 50
    longrange = args.maximum_event_size
    max_query_dist = 100000
    min_sv_align = 100

    alignments = load_alignments(args.coordsfile)
    sv_id_counter = 0
    output_lines = []

    for qid in sorted(alignments):
        refs = sorted(alignments[qid])
        qaligns = []
        for rid in refs:
            qaligns.extend(alignments[qid][rid])

        qaligns.sort(key=lambda alignment: alignment["qstart"])
        for index, alignment in enumerate(qaligns):
            alignment["qidx"] = index

        if len(qaligns) <= 1:
            continue

        for j in range(1, len(qaligns)):
            ai = qaligns[j - 1]
            aj = qaligns[j]
            rid = ai["rid"]

            if ai["rlen"] < min_sv_align or aj["rlen"] < min_sv_align:
                continue

            sv_id_counter += 1
            sv = classify_sv(
                ai,
                aj,
                rid,
                qid,
                narrow_threshold,
                longrange,
                max_query_dist,
            )

            if not passes_filters(
                sv,
                args.minimum_event_size,
                args.chromosome_filter,
                args.longrange_filter,
            ):
                continue

            if args.output_file == "bedpe":
                output_lines.append(format_bedpe_record(sv_id_counter, sv))
            else:
                output_lines.append(format_bed_record(sv_id_counter, sv))

    output = open(args.output_path, "w") if args.output_path else sys.stdout
    try:
        output.write("\n".join(output_lines))
        if output_lines:
            output.write("\n")
    finally:
        if args.output_path:
            output.close()


def main():
    parser = argparse.ArgumentParser(
        description="Find structural variants between adjacent alignments",
        usage=USAGE,
    )
    parser.add_argument("coordsfile", help="coords.tab file from unique anchor filtering")
    parser.add_argument("minimum_event_size", type=int, help="Minimum variant size")
    parser.add_argument("maximum_event_size", type=int, help="Maximum variant size")
    parser.add_argument(
        "chromosome_filter",
        choices=CHROMOSOME_FILTER_CHOICES,
        help="Chromosome filter mode",
    )
    parser.add_argument(
        "longrange_filter",
        choices=LONGRANGE_FILTER_CHOICES,
        help="Long-range variant filter mode",
    )
    parser.add_argument(
        "output_file",
        choices=OUTPUT_FILE_CHOICES,
        help="Output format",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_path",
        help="Write output to this file instead of stdout",
        default=None,
    )
    parser.set_defaults(func=run)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
