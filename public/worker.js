importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.1/full/pyodide.js");

let pyodide = null;
let resolveReady;
const readyPromise = new Promise(resolve => resolveReady = resolve);

async function init() {
    try {
        pyodide = await loadPyodide();
        await pyodide.loadPackage(["numpy", "pandas", "matplotlib"]);
        
        await pyodide.runPythonAsync(`
import matplotlib
matplotlib.use('Agg')
import os, sys, warnings
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
if os.getcwd() not in sys.path:
    sys.path.append(os.getcwd())
        `);

        // Fetch and mount scripts directly in the worker
        const scripts = [
            'Assemblytics_uniq_anchor.py', 'Assemblytics_between_alignments.py',
            'Assemblytics_within_alignment.py', 'Assemblytics_index.py',
            'Assemblytics_summary.py', 'Assemblytics_variant_charts.py',
            'Assemblytics_dotplot.py', 'Assemblytics_Nchart.py', 'Assemblytics.py'
        ];

        for (const script of scripts) {
            const response = await fetch(`../scripts/${script}`);
            const content = await response.text();
            pyodide.FS.writeFile(script, content);
        }

        self.postMessage({ type: 'status', message: 'Environment Ready' });
        resolveReady();
    } catch (err) {
        self.postMessage({ type: 'error', message: 'Initialization failed: ' + err.message });
    }
}

self.onmessage = async (e) => {
    const data = e.data;

    if (data.type === 'init') {
        await init();
    } else if (data.type === 'run') {
        await readyPromise;
        try {
            // Write input file
            pyodide.FS.writeFile('input.delta.gz', data.fileData);

            // Set up stdout/stderr redirection
            pyodide.setStdout({ batched: (str) => {
                if (str.startsWith("FILE_READY:")) {
                    const filename = str.split(":")[1].trim();
                    try {
                        const content = pyodide.FS.readFile(filename);
                        self.postMessage({ type: 'file_ready', name: filename, data: content });
                    } catch (e) {
                        console.error(`Worker failed to read ready file ${filename}: ${e}`);
                    }
                } else {
                    self.postMessage({ type: 'log', message: str, stream: 'python' });
                }
            }});
            pyodide.setStderr({ batched: (str) => self.postMessage({ type: 'log', message: str, stream: 'error' }) });

            await pyodide.runPythonAsync(`
import argparse
import os
from Assemblytics import run

print(f"Working directory: {os.getcwd()}")
print(f"Files: {os.listdir('.')}")

args = argparse.Namespace(
    delta="input.delta.gz",
    output_prefix="output",
    unique_length=${data.params.unique_length},
    minimum_size=${data.params.min_size},
    maximum_size=${data.params.max_size}
)
run(args)
            `);

            // Read outputs
            const files = pyodide.FS.readdir('.');
            const results = [];
            for (const file of files) {
                if (file.startsWith('output')) {
                    const content = pyodide.FS.readFile(file);
                    results.push({ name: file, data: content });
                }
            }

            self.postMessage({ type: 'done', results: results });

        } catch (err) {
            self.postMessage({ type: 'error', message: err.message });
        }
    }
};
