importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.1/full/pyodide.js");

let pyodide = null;

async function init() {
    try {
        pyodide = await loadPyodide();
        await pyodide.loadPackage(["numpy", "pandas", "matplotlib"]);
        
        await pyodide.runPythonAsync(`
import matplotlib
matplotlib.use('Agg')
import os
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
        `);

        self.postMessage({ type: 'status', message: 'Environment Ready' });
    } catch (err) {
        self.postMessage({ type: 'error', message: 'Initialization failed: ' + err.message });
    }
}

self.onmessage = async (e) => {
    const data = e.data;

    if (data.type === 'init') {
        await init();
    } else if (data.type === 'mount') {
        try {
            pyodide.FS.writeFile(data.name, data.content);
        } catch (err) {
            self.postMessage({ type: 'error', message: 'Mount failed: ' + err.message });
        }
    } else if (data.type === 'run') {
        try {
            // Write input file
            pyodide.FS.writeFile('input.delta.gz', data.fileData);

            // Set up stdout/stderr redirection
            pyodide.setStdout({ batched: (str) => self.postMessage({ type: 'log', message: str, stream: 'python' }) });
            pyodide.setStderr({ batched: (str) => self.postMessage({ type: 'log', message: str, stream: 'error' }) });

            await pyodide.runPythonAsync(`
import sys
import os
import argparse

# Force the current directory into sys.path
current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

print(f"Python path: {sys.path}")
print(f"Files in current directory: {os.listdir(current_dir)}")

try:
    from Assemblytics import run
    print("Successfully imported Assemblytics")
except ImportError as e:
    print(f"Failed to import Assemblytics: {e}")
    # Try absolute path import as fallback if needed, but the path insert should work
    raise

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
