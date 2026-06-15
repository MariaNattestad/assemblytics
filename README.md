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
- Python 3
    - argparse
    - numpy
    - pandas
    - matplotlib

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

## Command-line instructions

To run Assemblytics from the command-line, use the `scripts/Assemblytics.py` script. It orchestrates the entire pipeline from filtering to plotting.

All dependencies (Python 3 with `numpy`, `pandas`, and `matplotlib`) must be installed on your system.

To run Assemblytics:

```bash
scripts/Assemblytics.py -d <delta_file> -o <output_prefix>
```

Example using the provided *E. coli* sample:
```bash
scripts/Assemblytics.py -d input_examples/Ecoli.delta.gz -o ecoli_output

# The output should match the one in the public/user_data/ecoli folder.

# Defaults are unique_length=10000, minimum_size=50, maximum_size=10000. For small genomes (e.g. bacteria), you may want to reduce the unique_length to 1000.
```

## Local web app instructions
The whole web application can be downloaded and run locally, utilizing the graphical user interface and giving the added benefit of the interactive dot plot which is only available in the web version and cannot run from the CLI.

Notes for installation:
- Use a local server like [Apache](https://www.apachefriends.org/download.html) and follow the instructions there.
- Clone this repository into a folder called `assemblytics`, to make the `.htaccess` file point the server correctly to the `public/` folder, where the index.php and other pages and web app resources are located.
- Make sure to open up permissions in user_uploads and user_data so the webserver can read and write there. 
- It does not contain the examples as some of these are huge files.
