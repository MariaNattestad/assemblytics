# Assemblytics: a web analytics tool for the detection of variants from an assembly 

If you use Assemblytics, please cite our paper in Bioinformatics: http://www.ncbi.nlm.nih.gov/pubmed/27318204

The preprint is still freely available on the BioRxiv: https://www.biorxiv.org/content/10.1101/044925v1

## Input instructions
IMPORTANT: Assemblytics has been configured to work only with MUMmer3 and using the following alignment instructions. Running Assemblytics with any other delta file as input may give errors or miscallibrated results.

Upload a delta file to analyze alignments of an assembly to another assembly or a reference genome

1. Download and install [MUMmer 3](https://sourceforge.net/projects/mummer/files/)
2. Align your assembly to a reference genome using nucmer (from MUMmer package)
```bash
nucmer -maxmatch -l 100 -c 500 REFERENCE.fa ASSEMBLY.fa -prefix OUT
# Settings above are important for unique anchor filtering to work correctly in Assemblytics.
```
Consult the [MUMmer 3 manual](https://mummer.sourceforge.net/manual/) if you encounter problems.

3. Optional: Gzip the delta file to speed up upload (usually 2-4X faster)
```
gzip OUT.delta
```
Then use the OUT.delta.gz file for upload.

4. Upload the .delta or delta.gz file to Assemblytics

Important: Use only contigs rather than scaffolds from the assembly. This will prevent false positives when the number of Ns in the scaffolded sequence does not match perfectly to the distance in the reference.

The unique sequence length required represents an anchor for determining if a sequence is unique enough to safely call variants from, which is an alternative to the mapping quality filter for read alignment.

## Dependencies
- Python 3.8+ with `numpy`, `pandas`, and `matplotlib` (installed automatically by `pip install -e .`, see Installation below)
- [MUMmer 3](https://sourceforge.net/projects/mummer/files/) to generate the input delta file (see Input instructions above)

## How Assemblytics works

Assemblytics analyzes alignments of a "query" assembly to a "reference" genome (or another assembly) to identify structural variants. The pipeline consists of the following key steps:

1. **Unique Anchor Filtering:** For every alignment, Assemblytics calculates how much of the query sequence is "unique" (not covered by any other alignments). Alignments are only retained if they meet a minimum unique anchor length requirement (default 10,000 bp). This ensures that variants are called from high-confidence, non-repetitive regions.
2. **Calling Variants Between Alignments:** Assemblytics identifies variants that occur in the gaps between adjacent alignments of the same query sequence. These include insertions, deletions, and tandem expansions/contractions that occur when the assembly and reference don't quite meet up.
3. **Calling Variants Within Alignments:** The pipeline also scans within individual alignments for mismatches in the gap sizes on the reference vs. query side.
4. **Integration and Categorization:** All identified variants are combined and categorized by type (Insertion, Deletion, Tandem Expansion/Contraction, Repeat Expansion/Contraction) and size.
5. **Visualization and Summary:** Finally, the tool generates summary statistics and several plots, including a dot plot of filtered alignments, an Nchart of the assembly, and size distributions of all called variants.

## FAQ

### What do the different variant types mean? What is tandem expansion versus repeat expansion?

![variants types in Assemblytics](docs/variant_types_in_Assemblytics.jpg)

### What is unique anchor filtering for?
See this example showing the point of unique anchor filtering (from the bioRxiv preprint supplementary materials): ![unique anchor filtering](docs/unique_anchor_filtering.png)

<sub>
<b>Supplementary Figure 1 caption:</b> Each repetitive element in a genome assembly can map ambiguously to multiple locations in the reference genome. Delta-filter, a component of MUMmer, filters repetitive alignments using a longest-increasing subsequence (LIS) dynamic programming algorithm to select subsets of long, high-identity alignments while penalizing overlaps (Kurtz et al., 2004; Phillippy et al., 2008). In contrast, Assemblytics eliminates repeats lacking substantial unique anchoring sequence (default: 10 kb). <b>A</b>. Example: a simulated 20 kb contig sequence matches three locations in the reference except for a single nucleotide (red point) providing a better match on the right. <b>B</b>. Dot plot of all raw, unfiltered alignments from nucmer. <b>C</b>. Dot plot after <code>delta-filter -r</code> (equivalent to unfiltered). <b>D</b>. Dot plot after <code>delta-filter -q</code>; here, a single nucleotide is enough for <code>-q</code> to prefer the third alignment. <b>E</b>. Dot plot after Assemblytics unique anchor filtering: only alignments with at least 10 kb uniquely anchored sequence (aligning to a single position in the reference) are retained; the repeats are removed. Assemblytics annotates structural variants within such filtered gaps as repeat expansions or contractions, depending on whether the gap is larger in the query or reference, respectively. No variant is reported unless the gap size changes, so repeats themselves are not reported as SVs—only expansions (increased size) or contractions (decreased size) are.
</sub>

## Installation

```bash
pip install -e .
```

This installs the `assemblytics` package (the orchestrator and all of its pipeline stages live in `public/assemblytics/` -- it's kept inside `public/` so the same files are served directly to the web app, with no separate copy to keep in sync) along with an `assemblytics` console command. A versioned release on PyPI and an updated bioconda recipe are in progress (see `packaging/bioconda/meta.yaml` for a draft).

If you'd rather not install anything, you can run the pipeline directly from a clone: `cd public && python -m assemblytics.cli` instead of `assemblytics` in any command below (input/output paths are then relative to `public/`, e.g. `../input_examples/...`).

## Command-line instructions

The `assemblytics` command orchestrates the entire pipeline from filtering to plotting.

```bash
assemblytics -d <delta_file> -o <output_dir>
```

Example using the provided *E. coli* sample:
```bash
assemblytics -d input_examples/ecoli.delta.gz -o ecoli_output

# The output should match the one in the output_examples/ecoli folder.

# Defaults are unique_length=10000, minimum_size=50, maximum_size=10000. For small genomes (e.g. bacteria), you may want to reduce the unique_length to 1000.
```

By default, candidate variants that span two different reference chromosomes ("Interchromosomal") or that are larger than `--maximum_size` ("Longrange") are left out of the main results, since most of them come from misassemblies rather than real variants. Pass `--long-range` to also write these candidates to a separate `assemblytics_long_range_variants.bed`, so they're easy to find but clearly kept apart from the main, higher-confidence call set:

```bash
assemblytics -d input_examples/ecoli.delta.gz -o ecoli_output --long-range

# In addition to the usual output, this also writes ecoli_output/assemblytics_long_range_variants.bed.
# These candidates are usually misassemblies, but can occasionally be real translocations or
# other large-scale rearrangements -- review them manually before trusting them as true variants.
```

## Testing

`output_examples/` contains pre-computed results for five organisms, generated from the delta files in `input_examples/`. These are kept around (and untouched by any refactoring) specifically so the pipeline's correctness can be checked by re-running it and comparing the variant calls. The most important file to compare is `assemblytics_structural_variants.bed` (the combined, final set of structural variant calls) — everything else (plots, indices, summary stats) is derived from it.

To re-run the pipeline on each input and diff its variant calls against the matching example output:

```bash
# E. coli (uses a smaller unique anchor length since it's a small genome)
assemblytics -d input_examples/ecoli.delta.gz -o /tmp/assemblytics_test/ecoli -l 1000
diff <(tail -n +2 /tmp/assemblytics_test/ecoli/assemblytics_structural_variants.bed | sort) \
     <(tail -n +2 output_examples/ecoli/E__coli_example.Assemblytics_structural_variants.bed | sort) \
     && echo "ecoli: OK"

# Yeast (Saccharomyces cerevisiae)
assemblytics -d input_examples/yeast.delta.gz -o /tmp/assemblytics_test/yeast
diff <(tail -n +2 /tmp/assemblytics_test/yeast/assemblytics_structural_variants.bed | sort) \
     <(tail -n +2 output_examples/yeast/Saccharomyces_cerevisiae_example.Assemblytics_structural_variants.bed | sort) \
     && echo "yeast: OK"

# Arabidopsis thaliana
assemblytics -d input_examples/arabidopsis.delta.gz -o /tmp/assemblytics_test/arabidopsis
diff <(tail -n +2 /tmp/assemblytics_test/arabidopsis/assemblytics_structural_variants.bed | sort) \
     <(tail -n +2 output_examples/arabidopsis/Arabidopsis_example.Assemblytics_structural_variants.bed | sort) \
     && echo "arabidopsis: OK"

# Drosophila melanogaster
assemblytics -d input_examples/drosophila.delta.gz -o /tmp/assemblytics_test/drosophila
diff <(tail -n +2 /tmp/assemblytics_test/drosophila/assemblytics_structural_variants.bed | sort) \
     <(tail -n +2 output_examples/drosophila/Drosophila_example.Assemblytics_structural_variants.bed | sort) \
     && echo "drosophila: OK"

# Human (assembly aligned to hg19) -- the largest input, this one takes the longest to run
assemblytics -d input_examples/human.delta.gz -o /tmp/assemblytics_test/human
diff <(tail -n +2 /tmp/assemblytics_test/human/assemblytics_structural_variants.bed | sort) \
     <(tail -n +2 output_examples/human/Human_NA12878_to_hg19.Assemblytics_structural_variants.bed | sort) \
     && echo "human: OK"
```

(No `pip install -e .` yet? Run these from inside `public/` instead, replacing `assemblytics` with `python -m assemblytics.cli` and adjusting the `input_examples/`/`output_examples/` paths to `../input_examples/`/`../output_examples/`.)

Each `diff` should print nothing (no differences) followed by the "OK" line. The `tail -n +2` skips the header line, and `sort` makes the comparison order-independent since variant IDs can legitimately be assigned in a different order between runs.

## Local web app instructions

The web app (`public/`) runs the entire Assemblytics pipeline client-side in the browser via [Pyodide](https://pyodide.org/) (Python compiled to WebAssembly) and a Web Worker. There is no server-side code, no upload step, and no installation beyond a static file server — your delta file never leaves your machine.

To run it locally, serve the `public/` folder with any static file server, for example:

```bash
cd assemblytics
python3 -m http.server 8000 --directory public
# Then open http://localhost:8000 in your browser
```
