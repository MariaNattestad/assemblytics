.PHONY: wheel clean

wheel:
	python3 -m build --wheel --outdir dist/
	cp dist/assemblytics-*-py3-none-any.whl public/

clean:
	rm -rf dist/ build/ assemblytics.egg-info/
