importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.1/full/pyodide.js");

let pyodide = null;
let resolveReady;
const readyPromise = new Promise(resolve => resolveReady = resolve);

async function init() {
    try {
        pyodide = await loadPyodide();
        await pyodide.loadPackage(["numpy", "pandas", "matplotlib", "micropip"]);

        await pyodide.runPythonAsync(`
import matplotlib
matplotlib.use('Agg')
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
import micropip
await micropip.install('./assemblytics-2.0.1-py3-none-any.whl')
        `);

        self.postMessage({ type: 'status', message: 'Environment Ready' });
        resolveReady();
    } catch (err) {
        self.postMessage({ type: 'error', message: 'Initialization failed: ' + (err && (err.message || err.toString())) });
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
from assemblytics.cli import run

print(f"Working directory: {os.getcwd()}")
print(f"Files: {os.listdir('.')}")

args = argparse.Namespace(
    delta="input.delta.gz",
    output_dir=".",
    unique_length=${data.params.unique_length},
    minimum_size=${data.params.min_size},
    maximum_size=${data.params.max_size},
    long_range=False
)
run(args)
            `);

            // Read outputs
            const files = pyodide.FS.readdir('.');
            const results = [];
            for (const file of files) {
                if (file.startsWith('assemblytics_')) {
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
