////////////////////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////////
//////////////////////////////////////////      Dot Plot       /////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////////

var DotPlot = function(element, config) {

	this.element = element;

	this.config = config;
	this.data = undefined;

	this.parent = config.parent;

	this.state = {
		layout: {
			whole: {height: config.height, width: config.width},
			inner: {height: null, width: null, left: null, top: null},
		},
		allRefs: null,
		allQueries: null,
		selectedRefs: null,
		selectedQueries: null,
		dataByQuery: {},
		queryInfo: [],
		refInfo: [],
		queryIndex: {},
		annotationData: {},
		xAnnotations: [],
		yAnnotations: [],
		trackGetter: [],
		numDrawRequests: 0,
		zoom_stack: [],
	};

	this.scales = {x: null, y: null, zoom: {area: null, x: d3.scaleLinear(), y: d3.scaleLinear()}};

	this.k = { x: "ref", y: "query" };


	// Set up permanent DOM elements
	this.element
		.style("position","relative");

	this.canvas = this.element.append('canvas')
		.style("position", "absolute")
		.style("top", 0)
		.style("left", 0);

	this.context = this.canvas
			.node().getContext('2d');
	this.svg = this.element.append("svg")
		.style("position", "absolute")
		.style("top", 0)
		.style("left", 0);

	this.svg.append("rect").attr("class","innerBorder");
	this.svg.append("text").attr("class","xTitle");
	this.svg.append("g").attr("class","yTitle").append("text").attr("class","yTitle");

	this.svg.append("g").attr("class","innerPlot");
	this.svg.append("g").attr("class","brush");

	this.xAnnotations = this.svg.append("g");
	this.yAnnotations = this.svg.append("g");

	this.reset_styles();

}

DotPlot.prototype.setData = function(data) {
	this.data = data;

	// Set reference and query sequence sizes:
	this.state.allRefs = R.compose( R.uniq, R.map(String), R.map(R.props(["ref", "ref_length"])))(data);
	this.state.allQueries = R.compose( R.uniq, R.map(R.props(["query", "query_length"])))(data);

	this.initializePlot();


}

DotPlot.prototype.initializePlot = function(data) {
	this.state.selectedRefs = this.state.allRefs;
	this.state.selectedQueries = this.state.allQueries;

	// Store data indexed by query:

	this.state.dataByQuery = R.compose(R.map(R.groupBy(R.prop("tag"))), R.groupBy(R.prop("query")))(this.data);

	// scales
	this.setScalesFromSelectedSeqs();

	this.layoutPlot();
	this.initializeZoom()
	this.setScaleRanges();

	this.draw();
}

const stringFirst = function(d){
	return [String(d[0]), d[1]];
}

DotPlot.prototype.setCoords = function(coords, index) {
	this.coords = coords;

	this.parseIndex(index);
	

	this.state.allRefs = R.compose(R.map(stringFirst), R.map(R.props(["ref","ref_length"])))(this.state.refInfo);
	
	this.state.allQueries = R.compose(R.map(stringFirst), R.map(R.props(["query","query_length"])))(this.state.queryInfo);

	this.initializePlot();
}

DotPlot.prototype.calculateMemory = function(boundariesY) {
	const queryIndex = this.state.queryIndex;

	function memByQuery(query) {
		var uniq = queryIndex[query]["bytePosition_unique"];
		var rep = uniq + queryIndex[query]["bytePosition_repetitive"];
		var end = rep + queryIndex[query]["bytePosition_end"];
		var u = rep-uniq;
		var r = end-rep;
		if (queryIndex[query]["loaded_unique"]) {
			u = 0;
		}
		if (queryIndex[query]["loaded_repetitive"]) {
			r = 0;
		}

		return {unique: u, repetitive: r};
	}

	if (boundariesY !== undefined) {
		this.state.queries_in_view = R.pluck("name", boundariesY);
		var mems = R.map(memByQuery, this.state.queries_in_view);
		var memUnique = R.compose(R.sum, R.pluck("unique"))(mems);
		var memRepetitive = R.compose(R.sum, R.pluck("repetitive"))(mems);

		this.parent.updateMemoryButtons(memUnique, memRepetitive);
	}
}

DotPlot.prototype.loadAllInView = function(tag) {
	var _this = this;
	R.map(function(query) {
		_this.loadAlignmentsByQueryAndTag(query, tag);
	}, this.state.queries_in_view);
}

DotPlot.prototype.parseIndex = function(index) {

	var lines = index.split("\n");

	var refCSV = "";
	var queryCSV = "";
	var overviewCSV = "";
	var reading = "";

	for (var i in lines) {
		if (lines[i][0] === "#") {
			if (lines[i] === "#ref") {
				reading = "ref";
			} else if (lines[i] === "#query") {
				reading = "query";
			} else if (lines[i] === "#overview") {
				reading = "overview";
			} else {
				console.log("Unrecognized # line in index file:", lines[i]);
			}
		} else {
			if (reading == "ref") {
				refCSV += lines[i] + "\n";
			} else if (reading == "query") {
				queryCSV += lines[i] + "\n";
			} else if (reading == "overview") {
				overviewCSV += lines[i] + "\n";
			} else {
				console.log("Unrecognized line in index file:");
				console.log(lines[i]);
			}
		}
	}

	const parseCSV = function(CSVString) {
		var parsed = Papa.parse(CSVString, {header: true, dynamicTyping: true, skipEmptyLines: true});
		if (parsed.errors.length > 0) {
			console.log(CSVString)
			console.log(parsed.errors);

			throw "Error parsing index file";
		}
		return parsed.data;
	}

	const splitBySquiggly = R.curry(function(prop, arr) {
		return R.map(function(d) {d[prop] = String(d[prop]).split("~"); return d}, arr);
	});

	const stringifyProp = R.curry(function(prop, d) {
		d[prop] = String(d[prop]);
		return d;
	});

	this.state.refInfo = R.compose(R.map(stringifyProp("ref")), splitBySquiggly("matching_queries"), parseCSV)(refCSV);
	this.state.queryInfo =  R.compose(R.map(stringifyProp("query")), splitBySquiggly("matching_refs"), parseCSV)(queryCSV);

	this.state.queryIndex = R.zipObj(R.pluck("query", this.state.queryInfo), this.state.queryInfo);

	this.data = parseCSV(overviewCSV);
}


DotPlot.prototype.draw = function() {

	this.state.numDrawRequests += 1;
	var currentRequest = this.state.numDrawRequests;
	showSpinner(true, "draw");
	var _this = this;

	// Set up a stack of draw cycles: any draw requests within 100 ms of each other get bundled so only the last one executes
	setTimeout(function() {_this.drawRequested(currentRequest)}, 100);
}

DotPlot.prototype.drawRequested = function(numDrawRequests) {
	if (numDrawRequests === this.state.numDrawRequests) {
		if (numDrawRequests > 1) {
			console.log("number of draws skipped:", numDrawRequests-1)
		}

		this.drawGrid();
		this.drawAlignments();
		this.drawAnnotationTracks();
		this.state.numDrawRequests = 0;
		showSpinner(false, "draw", true);
	}
}

DotPlot.prototype.setScaleRanges = function() {
	//////////////////////////////////////    Set up scales for plotting    //////////////////////////////////////

	// Set scales with the correct inner size, but don't use them to translate, since we will be applying a translate in the draw function itself
	var xRange = [0, this.state.layout.inner.width];
	var yRange = [this.state.layout.inner.height, 0];
	this.scales.x.range(xRange);
	this.scales.y.range(yRange);
	this.scales.zoom.area = [[xRange[0], yRange[1]], [xRange[1], yRange[0]]];
	this.scales.zoom.x.domain(xRange).range(xRange);
	this.scales.zoom.y.domain(yRange).range(yRange);

}

DotPlot.prototype.setScalesFromSelectedSeqs = function() {
	this.scales.x = new MultiSegmentScale({data: this.state.selectedRefs, key_name: 0, length_name: 1});
	this.scales.y = new MultiSegmentScale({data: this.state.selectedQueries, key_name: 0, length_name: 1});

	this.scales.x.range([0, this.state.layout.inner.width]);
	this.scales.y.range([this.state.layout.inner.height, 0]);
}

function parseCoords(coords, query, tag) {

	var parsed = Papa.parse("ref_start,ref_end,query_start,query_end,ref\n" + coords, {header: true, dynamicTyping: true, skipEmptyLines: true});
	if (parsed.errors.length > 0) {
		console.log("Error parsing a chunk of the coords file");
		console.log(parsed.errors);
		console.log(coords);
	}

	return R.map(function(d) {d.query = query; d.tag = tag; return d}, parsed.data);
}

var setAlignments = R.curry(function(_this, query, tag, data) {
	var lines = data.split("\n");

	var content = {unique: "", repetitive: ""};
	var reading = undefined;
	for (var i in lines) {
		if (lines[i][0] === "!") {
			if (lines[i] == "!" + query + "!unique") {
				reading = "unique";
			} else if (lines[i] == "!" + query + "!repetitive") {
				reading = "repetitive";
			} else {
				reading = undefined;
			}
		} else if (reading !== undefined) {
			content[reading] += lines[i] + "\n";
		}
	}



	if (tag === "both") {
		var before = 0;
		if (_this.state.dataByQuery[query]["unique"]) {
			before = _this.state.dataByQuery[query]["unique"].length;
		}
		_this.state.dataByQuery[query]["unique"] = parseCoords(content["unique"], query, "unique");
		var after = _this.state.dataByQuery[query]["unique"].length;
		// console.log(query, ": Replaced overview of", before, "unique alignments with", after);

		before = 0;
		if (_this.state.dataByQuery[query]["repetitive"]) {
			before = _this.state.dataByQuery[query]["repetitive"].length;
		}
		_this.state.dataByQuery[query]["repetitive"] = parseCoords(content["repetitive"], query, "repetitive");
		var after = _this.state.dataByQuery[query]["repetitive"].length;
		// console.log(query, ": Replaced overview of", before, "repetitive alignments with", after);

	} else {
		var before = 0;
		if (_this.state.dataByQuery[query][tag]) {
			before = _this.state.dataByQuery[query][tag].length;
		}
		_this.state.dataByQuery[query][tag] = parseCoords(content[tag], query, tag);
		var after =  _this.state.dataByQuery[query][tag].length;

		// console.log(query, ": Replaced overview of", before, tag, "alignments with", after);
	}

	_this.draw();

});

DotPlot.prototype.loadAlignmentsByQueryAndTag = function(query, tag) {

	var uniq = this.state.queryIndex[query]["bytePosition_unique"];
	var rep = uniq + this.state.queryIndex[query]["bytePosition_repetitive"];
	var end = rep + this.state.queryIndex[query]["bytePosition_end"];

	if (this.state.dataByQuery[query] === undefined) {
		this.state.dataByQuery[query] = {};
	}

	if (tag === "unique" && !(this.state.queryIndex[query]["loaded_unique"])) {
		this.coords(uniq, rep, setAlignments(this, query, "unique"));
		this.state.queryIndex[query]["loaded_unique"] = true;
	} else if (tag === "repetitive" && !(this.state.queryIndex[query]["loaded_repetitive"])) {
		this.coords(rep, end, setAlignments(this, query, "repetitive"));
		this.state.queryIndex[query]["loaded_repetitive"] = true;
	}
}

DotPlot.prototype.seqSelectionDidChange = function() {
	this.setScalesFromSelectedSeqs();
	this.resetZoom();
}

DotPlot.prototype.resetRefQuerySelections = function(refNames) {
	this.state.selectedRefs = this.state.allRefs;
	this.state.selectedQueries = this.state.allQueries;

	this.seqSelectionDidChange();

}
DotPlot.prototype.selectRefs = function(refNames) {
	var state = this.state;

	state.selectedRefs = R.filter(function(d) {return R.contains(d[0], refNames)}, state.allRefs);
	
	var matchNames = R.filter(function(d) {return R.contains(d.ref, refNames)});
	var getQueries = R.compose(R.uniq, R.flatten, R.pluck("matching_queries"), matchNames);
	var queryNames = getQueries(state.refInfo);

	state.selectedQueries = R.filter(function(d) {return R.contains(d[0], queryNames)}, state.allQueries);


	this.seqSelectionDidChange();
}

DotPlot.prototype.selectQueries = function(queryNames) {
	var state = this.state;

	state.selectedQueries = R.filter(function(d) {return R.contains(d[0], queryNames)}, state.allQueries);

	var matchNames = R.filter(function(d) {return R.contains(d.query, queryNames)});
	var getRefs = R.compose(R.uniq, R.flatten, R.pluck("matching_refs"), matchNames);
	var refNames = getRefs(state.queryInfo);

	state.selectedRefs = R.filter(function(d) {return R.contains(d[0], refNames)}, state.allRefs);

	this.seqSelectionDidChange();
}

DotPlot.prototype.addAnnotationData = function(dataset) {
	if (this.state.annotationData[dataset.key] === undefined) {
		var plottableAnnotations = null;
		var side = null;

		if (R.any(R.equals(this.k.x), R.keys(dataset.data[0]))) {
			side = "x";
		} else if (R.any(R.equals(this.k.y), R.keys(dataset.data[0]))) {
			side = "y";
		} else {
			throw("annotation file does not contain ref or query in the header");
		}

		var seqSide = this.k[side];
		var annotSeqs = R.uniq(R.pluck(seqSide, dataset.data));

		var alignmentSeqs = (seqSide === "ref" ? R.pluck(0, this.state.allRefs) : R.pluck(0, this.state.allQueries));
		var tmpScale = (seqSide === "ref" ? new MultiSegmentScale({data: this.state.allRefs, key_name: 0, length_name: 1}) : new MultiSegmentScale({data: this.state.allQueries, key_name: 0, length_name: 1}));

		var sharedSeqs = R.intersection(alignmentSeqs, annotSeqs);
		var annotSeqsNotInAlignments = R.difference(annotSeqs, alignmentSeqs);
		if (annotSeqsNotInAlignments.length === annotSeqs.length) {
			showMessage("None of the annotations' sequence names match the alignments' sequence names", "danger");
			return;
		} else if (annotSeqsNotInAlignments.length > 0) {
			console.warn("Some annotations are on the following sequences that are not in the alignments input:", R.join(", ", annotSeqsNotInAlignments));
		}

		var annotMatches = function(d) {
			return tmpScale.contains(d[seqSide], d[seqSide+"_start"]) && tmpScale.contains(d[seqSide], d[seqSide+"_end"])
		};

		plottableAnnotations = R.filter(annotMatches, dataset.data);

		this.addAnnotationTrack({side: side, key: dataset.key, data: plottableAnnotations});
		this.state.annotationData[dataset.key] = plottableAnnotations;
	}
}

DotPlot.prototype.addAnnotationTrack = function(config) {

	var newTrack = undefined;
	if (config.side == "x") {
		newTrack = new Track({side: config.side, element: this.xAnnotations.append("g"), data: config.data, key: config.key, parent: this});
		this.state.xAnnotations.push(newTrack);
	} else if (config.side == "y") {
		newTrack = new Track({side: config.side, element: this.yAnnotations.append("g"), data: config.data, key: config.key, parent: this});
		this.state.yAnnotations.push(newTrack);
	} else {
		throw("in addAnnotationTrack, config.side must by 'x' or 'y'");
	}

	this.state.trackGetter[config.key] = newTrack;
	this.layoutPlot();
	this.initializeZoom()
	this.setScaleRanges();

	this.draw();
}

DotPlot.prototype.drawAnnotationTracks = function() {
	this.xAnnotations
		.attr("transform","translate(" + this.state.layout.annotations.x.left + "," + this.state.layout.annotations.x.top + ")");
	this.yAnnotations
		.attr("transform","translate(" + this.state.layout.annotations.y.left + "," + this.state.layout.annotations.y.top + ")");

	for (var i in this.state.xAnnotations) {
		this.state.xAnnotations[i].width(this.state.layout.inner.width);
		this.state.xAnnotations[i].draw();
	}
	for (var i in this.state.yAnnotations) {
		this.state.yAnnotations[i].height(this.state.layout.inner.height);
		this.state.yAnnotations[i].draw();
	}
}

DotPlot.prototype.zoomOut = function() {
	// Check for previous zoom states and use them, otherwise return to the original zoom
	var s = undefined;
	if (!R.isEmpty(this.state.zoom_stack)) {
		s = this.state.zoom_stack.pop();
	} else {
		s = this.scales.zoom.area;
		this.state.isZoomed = false;
	}

	this.scales.zoom.x.domain([s[0][0], s[1][0]]);
	this.scales.zoom.y.domain([s[1][1], s[0][1]]);
	this.draw();
}

DotPlot.prototype.resetZoom = function() {
	this.state.zoom_stack = [];
	this.zoomOut();
}

DotPlot.prototype.setZoom = function(zoomX, zoomY) {
	// Save the current zoom level to the zoom_stack
	const currentX = this.scales.zoom.x.domain();
	const currentY = this.scales.zoom.y.domain();
	this.state.zoom_stack.push([[currentX[0], currentY[1]], [currentX[1], currentY[0]]]);

	// Go to the new zoom level
	this.scales.zoom.x.domain(zoomX);
	this.scales.zoom.y.domain(zoomY);

	this.draw();
}

DotPlot.prototype.layoutPlot = function() {
	// Set up the static parts of the view that only change when width or height change, but not when zooming or changing data
	var paddingLeft = 120;
	var paddingBottom = 100;
	var paddingTop = 10;
	var paddingRight = 10;

	var annotationThicknessX = 0;
	for (var i in this.state.xAnnotations) {
		this.state.xAnnotations[i].top(annotationThicknessX);
		annotationThicknessX += this.state.xAnnotations[i].height();
	}
	var annotationThicknessY = 0;
	for (var i in this.state.yAnnotations) {
		this.state.yAnnotations[i].left(annotationThicknessY);
		annotationThicknessY += this.state.yAnnotations[i].width();
	}

	// Inside plotting area:
	this.state.layout.inner = {
		left: paddingLeft + annotationThicknessY,
		top: paddingTop,
		width: this.state.layout.whole.width - annotationThicknessY - paddingLeft - paddingRight,
		height: this.state.layout.whole.height - annotationThicknessX - paddingBottom - paddingTop,
	}

	this.state.layout.annotations = {
		x: {
			top: (this.state.layout.inner.top + this.state.layout.inner.height),
			left: this.state.layout.inner.left,
		},
		y: {
			top: (this.state.layout.inner.top),
			left: this.state.layout.inner.left - annotationThicknessY,
		}
	}

	this.state.layout.outer = {
		left: paddingLeft,
		top: paddingTop,
		width: this.state.layout.inner.width + annotationThicknessY,
		height: this.state.layout.inner.height + annotationThicknessX,
	}

	this.svg
		.attr("width", this.state.layout.whole.width)
		.attr("height", this.state.layout.whole.height);

	this.svg.select("g.innerPlot")
		.attr("transform", "translate(" + this.state.layout.inner.left + "," + this.state.layout.inner.top + ")");

	this.svg.select("g.brush")
		.attr("transform", "translate(" + this.state.layout.inner.left + "," + this.state.layout.inner.top + ")");

	this.canvas
		.style("top", this.state.layout.inner.top + "px")
		.style("left", this.state.layout.inner.left + "px")
		.attr('width', this.state.layout.inner.width)
		.attr('height', this.state.layout.inner.height);



	// Draw outside border rectangle
	// c.setTransform(1, 0, 0, 1, 0, 0);
	// c.strokeStyle = "#f0f";
	// c.rect(0,0,this.state.layout.whole.width,this.state.layout.whole.height);
	// c.stroke();

	////////////////////////////////////////    Borders    ////////////////////////////////////////

	// Inner plot border
	this.svg.select("rect.innerBorder")
		.attr("x", this.state.layout.inner.left)
		.attr("y", this.state.layout.inner.top)
		.attr("width", this.state.layout.inner.width)
		.attr("height", this.state.layout.inner.height)
		.style("fill","transparent")
		.style("stroke","black");

	//////////////////////////////////////    Axis titles    //////////////////////////////////////

	// Ref
	this.svg.select("text.xTitle")
		.attr("x", this.state.layout.inner.left + this.state.layout.inner.width/2)
		.attr("y", this.state.layout.whole.height-10)
		.style("dominant-baseline","middle")
		.style("text-anchor","middle")
		.style("font-size", 20);

	// Query
	this.svg.select("g.yTitle")
		.attr("transform", "translate(20," + this.state.layout.inner.height/2 + ")")
		.select("text.yTitle")
			.attr("transform", "rotate(-90)")
			.style("dominant-baseline","middle")
			.style("text-anchor","middle")
			.style("font-size", 20);

}

DotPlot.prototype.initializeZoom = function() {
	// Intialize brush to zoom functionality
	var plot = this;
	var brush = d3.brush()
		.extent([[0, 0], [plot.state.layout.inner.width, plot.state.layout.inner.height]])
		.on("end", brushended);

	var brushArea = this.svg.select("g.brush").call(brush);

	var x = plot.scales.zoom.x;
	var y = plot.scales.zoom.y;


	function zoom(s) {
		const zoomX = [s[0][0], s[1][0]].map(x.invert, x);
		const zoomY = [s[1][1], s[0][1]].map(y.invert, y);

		plot.setZoom(zoomX, zoomY);
		brushArea.call(brush.move, null);
	}

	var idleTimeout, idleDelay = 350;

	function idled() {
		idleTimeout = null;
	}

	plot.state.isZoomed = true;

	function brushended() {
		var s = d3.event.selection;
		if (s !== null) {
			zoom(s);
			plot.state.isZoomed = true;
		} else {
			// check for double-click
			if (!idleTimeout) {
				return idleTimeout = setTimeout(idled, idleDelay);
			}
			// zoom out
			if (plot.state.isZoomed) {
				plot.zoomOut();
			} else {
				plot.resetRefQuerySelections();
			}

		}
	}
}


function zoomFilterSnap(area, zoomScales, side) {
	var xOrY = (side == "x" ? 0 : 1);
	var zoom = zoomScales[side];

	var inside = R.curry(function(xOrY, point) {
		return (point >= area[0][xOrY] && point <= area[1][xOrY]);
	});

	var overlaps = R.curry(function(xOrY, d) {
		return (!((d.start < area[0][xOrY] && d.end < area[0][xOrY]) || (d.start > area[1][xOrY] && d.end > area[1][xOrY])));
	});

	var zoomTransform = R.map(function(d) {d.start = zoom(d.start); d.end = zoom(d.end); return d});
	var zoomFilter = function(xOrY) {
		return R.filter(overlaps(xOrY));
	}
	var zoomSnap = function(xOrY) {
		return R.map(function(d) {
			const basesPerPixel = d.length/(Math.abs(d.end-d.start));
			d.startBases = 0;
			if (!inside(xOrY)(d.start)) {
				d.startBases = Math.round(basesPerPixel * Math.abs(d.start-area[xOrY][xOrY]));
				d.start = area[xOrY][xOrY];
			}
			d.endBases = d.length;
			if (!inside(xOrY)(d.end)) {
				d.endBases = Math.round(d.length - (basesPerPixel * Math.abs(d.end-area[Number(!xOrY)][xOrY])));
				d.end = area[Number(!xOrY)][xOrY];
			}
			// d.basesPerPixel = basesPerPixel;
			// d.basesShown1 = basesPerPixel*Math.abs(d.end-d.start);
			// d.basesShown2 = d.endBases - d.startBases;
			return d;
		});
	};
	return R.compose(zoomSnap(xOrY), zoomFilter(xOrY), zoomTransform);
}
const baseFormat = function(x) {
	if (x === 0) {
		return "0";
	}
	return `${Math.round(x/10000)/100} Mb`;
}


DotPlot.prototype.drawGrid = function() {

	var c = this.context;

	// Translate everything relative to the inner plotting area
	c.setTransform(1, 0, 0, 1, 0, 0);


	// Ref
	this.svg.select("text.xTitle")
		.text(this.styles["x-axis title"]);

	// Query
	this.svg.select("g.yTitle")
		.select("text.yTitle")
			.text(this.styles["y-axis title"]);

	/////////////////////////////////////////    Grid and axis labels    //////////////////////////////////////////

	var area = this.scales.zoom.area;

	var boundariesX = zoomFilterSnap(area, this.scales.zoom, "x")(this.scales.x.getBoundaries());
	var boundariesY = zoomFilterSnap(area, this.scales.zoom, "y")(this.scales.y.getBoundaries());

	this.calculateMemory(boundariesY);

	var gridWidth = 0.2; // this.styles["width of reference grid lines"]

	var gridColor = "#000000" ; // this.styles["color of reference grid lines"]

	const showRefGrid = this.styles["show grid lines (reference)"];

	var displayGridRef = function(d) {if (Math.abs(d.end - d.start) > 5) {return "block"} else {return "none"}};
	if (showRefGrid === "always") {
		displayGridRef = "block";
	}
	else if (showRefGrid === "never") {
		displayGridRef = "none";
	}

	////////////////////////    Grid    //////////////////////

	var verticalLines = this.svg.select("g.innerPlot")
		.selectAll("line.verticalGrid").data(boundariesX);

	var newVerticalLines = verticalLines.enter().append("line")
		.attr("class","verticalGrid");

	verticalLines.merge(newVerticalLines)
		.style("stroke", gridColor)
		.style("stroke-width", gridWidth)
		.style("display", displayGridRef)
		.attr("x1", function(d) {return d.start})
		.attr("y1", 0)
		.attr("x2", function(d) {return d.start})
		.attr("y2", this.state.layout.inner.height);

	verticalLines.exit().remove();

	const showQueryGrid = this.styles["show grid lines (query)"];

	var displayGridQuery = function(d) {if (Math.abs(d.end - d.start) > 5) {return "block"} else {return "none"}};
	if (showQueryGrid === "always") {
		displayGridQuery = "block";
	}
	else if (showQueryGrid === "never") {
		displayGridQuery = "none";
	}

	var horizontalLines = this.svg.select("g.innerPlot")
		.selectAll("line.horizontalGrid").data(boundariesY);

	var newHorizontalLines = horizontalLines.enter().append("line")
		.attr("class","horizontalGrid");

	horizontalLines.merge(newHorizontalLines)
		.style("stroke", gridColor)
		.style("stroke-width", gridWidth)
		.style("display", displayGridQuery)
		.attr("x1", 0)
		.attr("y1", function(d) {return d.start})
		.attr("x2", this.state.layout.inner.width)
		.attr("y2", function(d) {return d.start});

	horizontalLines.exit().remove();

	/////////////////////////////////////////////////////////////////////////////////////////////////////
	////////////////////////////////////////////    Labels   ////////////////////////////////////////////
	/////////////////////////////////////////////////////////////////////////////////////////////////////

	var _this = this;

	function displayName(d) {
		if (Math.abs(d.end - d.start) > 5) {
			return d.name;
		} else {
			return ".";
		}
	}

	///////////////////     Sequence labels on X-axis    ///////////////////

	function setRef(d, i) {
		_this.selectRefs([d.name]);
	}

	var xLabels = this.svg.select("g.innerPlot")
		.selectAll("g.xLabels").data(boundariesX);

	var newXLabels = xLabels.enter().append("g")
		.attr("class","xLabels")

	xLabels.exit().remove();

	newXLabels.append("text")
		.style("text-anchor","end");

	var labelHeight = this.state.layout.outer.height + this.styles["font size (X-axis labels)"];
	xLabels = xLabels.merge(newXLabels)
		.attr("transform",function(d) {return "translate(" + (d.start+d.end)/2 + "," + labelHeight + ")"})

	var rotation = this.styles["rotate x-axis labels"] ? -45 : 0;
	xLabels.select("text")
			.text(displayName)
			.attr("transform", `rotate(${rotation})`)
			.style("font-size", this.styles["font size (X-axis labels)"])
			.style("cursor", "pointer")
			.on("click", setRef);

	///////////////////     Sequence labels on Y-axis    ///////////////////

	function setQuery(d, i) {
		_this.selectQueries([d.name]);
	}

	var inner = this.state.layout.inner;

	var yLabels = this.svg.select("g.innerPlot")
		.selectAll("text.yLabels").data(boundariesY);

	var yLabelLeft = -10 + this.state.layout.annotations.y.left - this.state.layout.inner.left;
	yLabels.exit().remove();

	var newYLabels = yLabels.enter().append("text")
		.attr("class","yLabels")
		.style("text-anchor","end")

	var yLabels = yLabels.merge(newYLabels)
		.attr("x", yLabelLeft)
		.attr("y", function(d) {return inner.top + (d.start+d.end)/2})
		.text(displayName)
		.style("font-size", this.styles["font size (Y-axis labels)"])
		.style("cursor", "pointer")
		.on("click", setQuery);

	///////////////////     Base-pair labels on X-axis    ///////////////////

	const padding = 5;

	var displayBasepairs = function(d) {if (Math.abs(d.end - d.start) > 70) {return "block"} else {return "none"}};

	var showBaseCoordinatesX = this.styles["show basepair coordinates markers for reference"];

	var basepairLabelsX = this.svg.select("g.innerPlot")
		.selectAll("g.basepairLabelsX").data(boundariesX);

	basepairLabelsX.exit().remove();

	var newBasepairLabelsX = basepairLabelsX.enter().append("g")
		.attr("class", "basepairLabelsX")

	newBasepairLabelsX.append("text").attr("class","start");
	newBasepairLabelsX.append("text").attr("class","end");


	var basepairLabelsX = basepairLabelsX.merge(newBasepairLabelsX);

	basepairLabelsX
		.style("display", showBaseCoordinatesX ? "block" : "none")
		.attr("transform", `translate(0, ${labelHeight + padding})`);

	// Show start coordinate
	basepairLabelsX.select("text.start")
		.attr("x", function(d) {return d.start + padding})
		.style("text-anchor","start")
		.style("display", displayBasepairs)
		.style("dominant-baseline","text-before-edge")
		.style("font-size", this.styles["font size (basepair coordinates)"])
		.text(function(d) {return baseFormat(d.startBases)});

	// Show end coordinate
	basepairLabelsX.select("text.end")
		.attr("x", function(d) {return d.end - padding})
		.style("text-anchor","end")
		.style("display", displayBasepairs)
		.style("dominant-baseline","text-before-edge")
		.style("font-size", this.styles["font size (basepair coordinates)"])
		.text(function(d) {return baseFormat(d.endBases)});


	///////////////////     Base-pair labels on Y-axis    ///////////////////

	var showBaseCoordinatesY = this.styles["show basepair coordinates markers for query"];

	var basepairLabelsY = this.svg.select("g.innerPlot")
		.selectAll("g.basepairLabelsY").data(boundariesY);


	basepairLabelsY.exit().remove();

	var newBasepairLabelsY = basepairLabelsY.enter().append("g")
		.attr("class", "basepairLabelsY")
	
	newBasepairLabelsY.append("text").attr("class","start");
	newBasepairLabelsY.append("text").attr("class","end");
	

	var basepairLabelsY = basepairLabelsY.merge(newBasepairLabelsY);

	basepairLabelsY
		.style("display", showBaseCoordinatesY ? "block" : "none")
		.attr("transform", `translate(${yLabelLeft-padding}, 0)`);

	// Show start coordinate
	basepairLabelsY.select("text.start")
		.attr("y", function(d) {return d.start - padding})
		.style("text-anchor","end")
		.style("dominant-baseline","ideographic")
		.style("display", displayBasepairs)
		.style("font-size", this.styles["font size (basepair coordinates)"])
		.text(function(d) {return baseFormat(d.startBases)});

	// Show end coordinate
	basepairLabelsY.select("text.end")
		.attr("y", function(d) {return d.end})
		.style("text-anchor","end")
		.style("dominant-baseline","text-before-edge")
		.style("display", displayBasepairs)
		.style("font-size", this.styles["font size (basepair coordinates)"])
		.text(function(d) {return baseFormat(d.endBases)});

	// Record positions for links
	this.parent.updateLinkPositions(boundariesX);
}

DotPlot.prototype.drawAlignments = function() {
	var c = this.context;

	/////////////////////////////////////////    Alignments    /////////////////////////////////////////

	var state = this.state;
	var scales = this.scales;
	var x = this.k.x;
	var y = this.k.y;

	// Draw lines
	c.setTransform(1, 0, 0, 1, 0, 0);
	c.clearRect(0, 0, this.state.layout.inner.width, this.state.layout.inner.height);

	var zoomX = this.scales.zoom.x;
	var zoomY = this.scales.zoom.y;

	function getLine(d) {
		return {
			start: {
				x: zoomX(scales.x.get(d[x], d[x + '_start'])),
				y: zoomY(scales.y.get(d[y], d[y + '_start']))
			},
			end: {
				x: zoomX(scales.x.get(d[x], d[x + '_end'])),
				y: zoomY(scales.y.get(d[y], d[y + '_end']))
			}
		};
	}
	var area = scales.zoom.area;

	function bothEndsLeft(line) {
		return (line.start.x < area[0][0] && line.end.x < area[0][0])
	}
	function bothEndsRight(line) {
		return (line.start.x > area[1][0] && line.end.x > area[1][0])
	}
	function bothEndsAbove(line) {
		return (line.start.y < area[0][1] && line.end.y < area[0][1])
	}
	function bothEndsBelow(line) {
		return (line.start.y > area[1][1] && line.end.y > area[1][1])
	}

	var tagColors = {repetitive: {forward: this.styles["color of repetitive alignments"], reverse: this.styles["color of repetitive alignments"]}, unique: {forward: this.styles["color of unique forward alignments"], reverse: this.styles["color of unique reverse alignments"]}};


	var count = 0;
	var drawLine = function(d) {
		var line = getLine(d);
		if (!(bothEndsAbove(line) || bothEndsBelow(line) || bothEndsLeft(line) || bothEndsRight(line))) {
			c.moveTo(line.start.x, line.start.y);
			c.lineTo(line.end.x, line.end.y);
		}
		count++;
	};

	var dotSize = this.styles["alignment line thickness"];

	var drawCircles = function(d) {
		var line = getLine(d);
		if (!(bothEndsAbove(line) || bothEndsBelow(line) || bothEndsLeft(line) || bothEndsRight(line))) {
			c.beginPath();
			c.fillStyle = getColor(d);
			c.arc(line.start.x, line.start.y, dotSize, 0, 2*Math.PI);
			c.arc(line.end.x, line.end.y, dotSize, 0, 2*Math.PI);
			c.fill();
		}
	}

	var showRepetitiveAlignments = this.styles["show repetitive alignments"];
	var thickness = this.styles["alignment line thickness"];
	var minAlignmentLength = this.styles["minimum alignment length"];

	var forward = function(d) {
		return (d.query_start <= d.query_end);
	}

	var reverse = function(d) {
		return (d.query_start > d.query_end);
	}

	var getColor = function(d) {
		if (forward(d)) {
			return tagColors[d.tag].forward;
		} else {
			return tagColors[d.tag].reverse;
		}
	}

	var longEnough = function(d) {
		return (d.ref_end-d.ref_start) >= minAlignmentLength;
	}

	for (var tag in tagColors) {
		if (tag === "unique" || showRepetitiveAlignments) {
			R.map(function(queryInfo) {
				var query = queryInfo[0];
				if (state.dataByQuery[query] !== undefined && state.dataByQuery[query][tag] !== undefined) {
					c.beginPath();
					c.strokeStyle = tagColors[tag].forward;
					c.lineWidth = thickness;
					R.compose(R.map(drawLine), R.filter(forward), R.filter(longEnough))(state.dataByQuery[query][tag]);
					c.stroke();

					c.beginPath();
					c.strokeStyle = tagColors[tag].reverse;
					c.lineWidth = thickness;
					R.compose(R.map(drawLine), R.filter(reverse), R.filter(longEnough))(state.dataByQuery[query][tag]);
					c.stroke();
				}
			}, state.selectedQueries);
		}
	}

	var filterAndDrawCircles = R.compose(R.map(drawCircles), R.filter(longEnough));

	if (this.styles["alignment symbol"] == "dotted ends") {
		for (var tag in tagColors) {
			if (tag === "unique" || showRepetitiveAlignments) {
				R.map(function(queryInfo) {
					var query = queryInfo[0];
					if (state.dataByQuery[query] !== undefined && state.dataByQuery[query][tag] !== undefined) {
						filterAndDrawCircles(state.dataByQuery[query][tag]);
					}
				}, state.selectedQueries);
			}
		}
	}

	console.log("Number of alignments drawn:", count);
}

DotPlot.prototype.style_schema = function() {
	var styles = [
		{name: "Fundamentals", type: "section"},
		{name: "x-axis title", type: "string", default: "reference"},
		{name: "y-axis title", type: "string", default: "query"},

		{name: "Alignments", type: "section"},
		{name: "show repetitive alignments", type: "bool", default: true},
		{name: "minimum alignment length", type: "number", default: 0},
		{name: "alignment symbol", type: "selection", default:"dotted ends", options: ["line","dotted ends"]},
		{name: "alignment line thickness", type: "number", default: 2},
		{name: "color of unique forward alignments", type: "color", default: "#0081b0"},
		{name: "color of unique reverse alignments", type: "color", default: "#87ba2d"},
		{name: "color of repetitive alignments", type: "color", default: "#ef8717"},

		{name: "Sequence labels", type: "section"},
		{name: "rotate x-axis labels", type: "bool", default: true},
		{name: "font size (X-axis labels)", type: "number", default: 10},
		{name: "font size (Y-axis labels)", type: "number", default: 10},

		{name: "Grid lines", type: "section"},
		{name: "show grid lines (reference)", type: "selection", default: "always", options: ["always", "zoom", "never"]},
		{name: "show grid lines (query)", type: "selection", default: "never", options: ["always", "zoom", "never"]},
		{name: "show basepair coordinates markers for reference", type: "bool", default: true},
		{name: "show basepair coordinates markers for query", type: "bool", default: true},
		{name: "font size (basepair coordinates)", type: "number", default: 10},

	];

	return styles;
}

DotPlot.prototype.reset_styles = function() {
	var style_schema = this.style_schema();
	this.styles = {};
	for (var i in style_schema) {
		this.styles[style_schema[i].name] = style_schema[i].default;
	}
}

DotPlot.prototype.set_style = function(style,value) {

	this.styles[style] = value;

	this.draw();
}

DotPlot.prototype.updateTrackSelections = function(selectedKey) {
	for (var key in this.state.trackGetter) {
		this.state.trackGetter[key].updateSelected(key === selectedKey);
	}
}

////////////////////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////////
//////////////////////////////////////////      Track       ////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////////

var Track = function(config) {
	this.element = config.element;

	this.element.attr("class", "Track");

	this.parent = config.parent;

	this.state = {left: 0, top: 0, height: 30, width: 30};
	this.side = config.side;

	this.key = config.key;
	this.data = config.data;
	this.reset_styles();


	// Create handle for editing the track
	this.editHandle = this.element.append("g")
		.style("z-index", 100000)
		.attr("class", "editHandle")
		.style('visibility', 'hidden')
		.style("cursor", "pointer");

	this.editHandle.append("rect")
		.style("fill","lightblue");

	this.editHandle.append("text")
		.style("font-family", "FontAwesome")
		.style("dominant-baseline","middle")
		.style("text-anchor","middle")
		.text('\uf040');

	this.editHandle.append("path");


	// Create background
	this.element.append("rect")
		.attr("class","trackBackground");
	this.element.append("g").attr("class", "annotation_group");
}



Track.prototype.top = function(newTop) {
	if (newTop === undefined) {
		return this.state.top;
	} else {
		this.state.top = newTop;
	}
}

Track.prototype.left = function(newLeft) {
	if (newLeft === undefined) {
		return this.state.left;
	} else {
		this.state.left = newLeft;
	}
}

Track.prototype.height = function(newHeight) {
	if (newHeight === undefined) {
		return this.state.height;
	} else {
		this.state.height = newHeight;
	}
}

Track.prototype.width = function(newWidth) {
	if (newWidth === undefined) {
		return this.state.width;
	} else {
		this.state.width = newWidth;
	}
}

var colorScale = d3.scaleOrdinal(d3.schemeAccent);

Track.prototype.drawEditHandle = function() {
	var _track = this;
	var xOrY = this.side;

	const handleSize = Math.min(this.state.height, this.state.width);

	var editHandle = this.editHandle;

	editHandle.on("click", function() {_track.editClicked()});

	if (xOrY === "x") {
		editHandle
			.attr("transform",`translate(${-handleSize},0)`);

		editHandle.selectAll("path")
			.attr("d", d3.symbol().type(d3.symbolTriangle).size(20))
			.attr("transform", `rotate(90) translate(${handleSize/2}, ${-handleSize+5})`);

	} else if (xOrY === "y") {
		editHandle
			.attr("transform",`translate(0, ${this.state.height})`);

		editHandle.selectAll("path")
			.attr("d", d3.symbol().type(d3.symbolTriangle).size(20))
			.attr("transform", `translate(${handleSize/2}, 5)`);
	}

	editHandle.selectAll("rect")
		.style("width", handleSize)
		.style("height", handleSize)

	editHandle.selectAll("text")
		.attr("x", (+handleSize/2))
		.attr("y", (handleSize/2));

	function mouseover() {
		editHandle.style("visibility","visible");
	}

	function mouseout() {
		if (!_track.selected) {
			editHandle.style("visibility","hidden");
		}
	}

	this.element.on("mouseover", mouseover);
	this.element.on("mouseout", mouseout);

}

var midArrowPathGenerator = R.curry(function(arrowSize, d) {
	var arrow = -1*arrowSize,
		x1 = 0,
		x2 = d.end-d.start,
		y = 0,
		direction = Number(d.strand=="+")*2-1;
	var xmid = (x1 + x2)/2;

	return (
		"M " + x1     					+ " " + y
	 + " L " + xmid   					+ " " + y
	 + " L " + (xmid + arrow*direction) + " " + (y + arrow)
	 + " L " + xmid   					+ " " + y
	 + " L " + (xmid + arrow*direction) + " " + (y - arrow)
	 + " L " + xmid   					+ " " + y
	 + " L " + x2   					+ " " + y);
});




var endArrowPathGenerator = R.curry(function(arrowSize, d) {
	var arrow = -1*arrowSize,
		x1 = 0,
		x2 = d.end-d.start,
		y = 0,
		direction = Number(d.strand=="+")*2-1;
	var xmid = (x1 + x2)/2;

	if (d.strand === "+") {
		return (
			"M " + x1     					+ " " + y
		 + " L " + x2   					+ " " + y
		 + " L " + (x2 + arrow*direction) 	+ " " + (y + arrow)
		 + " L " + x2   					+ " " + y
		 + " L " + (x2 + arrow*direction) 	+ " " + (y - arrow)
		 + " L " + x2   					+ " " + y);
	} else {
		return (
			"M " + x1     					+ " " + y
		 + " L " + (x1 + arrow*direction) 	+ " " + (y + arrow)
		 + " L " + x1   					+ " " + y
		 + " L " + (x1 + arrow*direction) 	+ " " + (y - arrow)
		 + " L " + x1   					+ " " + y
		 + " L " + x2   					+ " " + y);
	}

});

// resolveDirection : {strand {'+', '-', other}, degree [-180,180)} -> {degree, degree-180}
const resolveDirection = (strand, degree) =>
	R.cond([
		  [R.equals('+'), R.always(degree)],
		  [R.equals('-'), R.always(degree-180)],
		  [R.T, R.always(degree)]
	])(strand);


Track.prototype.drawAnnotationSymbols = function() {
	const _track = this;

	var xOrY = _track.side;
	var scale = _track.parent.scales[xOrY];

	var refOrQuery = _track.parent.k[xOrY];

	var annotMatches = function(d) {
		return scale.contains(d[refOrQuery], d[refOrQuery+"_start"]) && scale.contains(d[refOrQuery], d[refOrQuery+"_end"])
	};

	function scaleAnnot(d) {
		let obj = {
			start: scale.get(d[refOrQuery], d[refOrQuery + '_start']),
			end: scale.get(d[refOrQuery], d[refOrQuery + '_end']),
			seq: d[refOrQuery],
			length: d[refOrQuery + '_end'] - d[refOrQuery + '_start'],
			name: d.name,
			hover: d.name + " (" + d[refOrQuery] + ":" + d[refOrQuery + '_start'] + "-" + d[refOrQuery + '_end'] + ")",
		};
		return d.strand ? R.merge(obj, { strand: d.strand} ) : obj;
	}

	var minFeatureLength = _track.styles["minimum feature length (bp)"];
	var longEnough = function(d) {
		return d.length >= minFeatureLength;
	}

	var dataToPlot = R.compose(R.filter(longEnough), R.map(scaleAnnot), R.filter(annotMatches))(_track.data);

	let takeKLongest = R.compose(R.take(_track.styles["k longest annotations"] || 100),
		 R.sort(R.comparator((a,b) =>
		 			R.gt(R.prop('length', a), R.prop('length', b))
		 ))
	);
	let dataZoomed = R.compose(takeKLongest, zoomFilterSnap(_track.parent.scales.zoom.area, _track.parent.scales.zoom, xOrY))(dataToPlot);
	var shiftY = _track.parent.state.layout.inner.height;

	if (xOrY === "y") {
		dataZoomed = R.map(d => {
			d.start = shiftY - d.start;
			d.end = shiftY - d.end;
			return d
		}, dataZoomed);
	}

	var _app = _track.parent.parent;

	let annotGroup = _track.element.select(".annotation_group");

	if (xOrY === "y") {
		annotGroup.attr("transform", `translate(0,${shiftY}) rotate(-90)`);
	}

	let annots = annotGroup.selectAll(".annot").data(dataZoomed);

	let newAnnots = annots.enter().append("g").attr("class", "annot");
	newAnnots.append("rect");
	newAnnots.append("path");
	newAnnots.append("text");


	annots.exit().remove();

	annots = annots.merge(newAnnots);

	annots.on("click", function(d) {_app.showInInspector(d.hover)});

	var trackThickness = xOrY === "x" ? _track.height() : _track.width();

	var annotThickness = trackThickness / 2;
	var position = (trackThickness - annotThickness) / 2;


	annots.attr("transform", d => `translate(${d.start}, ${position})`);

	if (this.styles["show rectangles"]) {
		const opacity = _track.styles["rectangle opacity"];
		annots.select("rect")
			.style("visibility", "visible")
			.attr("fill", d => colorScale(d.seq))
			.attr("stroke", d => colorScale(d.seq))
			.attr("stroke-width", 1)
			.attr("opacity", opacity);

		annots.select("rect")
			.attr("width", function(d) {return d.end-d.start})
			.attr("height", annotThickness);
	} else {
		annots.select("rect")
			.style("visibility", "hidden")
	}

	if (_track.styles["show arrows based on strands"]) {

		annots.select("path")
			.attr("transform",
				(d) => `translate(0, ${(annotThickness/2)})`);

		var arrowFunction = endArrowPathGenerator(annotThickness/2);
		switch (_track.styles["arrow style"]) {
			case "triangle":
				arrowFunction = d3.symbol().type(d3.symbolTriangle).size(annotThickness);

				annots.select("path")
					.attr("transform",
						(d) => `translate(${(d.end-d.start)/2}, ${(annotThickness/2)}) rotate(${'strand' in d ? resolveDirection(d.strand, 90) : 90})`);
				break;
			case "arrow at the end":
				arrowFunction = endArrowPathGenerator(annotThickness/2);
				break;
			case "arrow in the middle":
				arrowFunction = midArrowPathGenerator(annotThickness/2);
				break;
		}

		annots.select("path")
			.style("visibility", "visible")
			.attr("fill", d => colorScale(d.seq))
			.attr("stroke-width", 2)
			.attr("stroke", (d) => colorScale(d.seq))
			.attr("d", arrowFunction);


	}  else {
		annots.select("path")
			.style("visibility", "hidden")
	}

	if (_track.styles["show names"]) {
		const fontSize = this.styles["font size"];
		annots.select("text")
			.style("visibility", "visible")
			.attr("fill", d => colorScale(d.seq))
			.style("dominant-baseline","middle")
			.style("text-anchor","middle")
			.style("font-size", fontSize)
			.text(d => d.name);
		if (xOrY === "y") {
			annots.select("text")
				.attr("transform","rotate(180)");
		}

		annots.select("text")
			.attr("x", function(d) {return (d.end-d.start)/2});
	}  else {
		annots.select("text")
			.style("visibility", "hidden")
	}

}

Track.prototype.draw = function() {
	const _track = this;
	_track.element.attr("transform", "translate(" + this.state.left + "," + this.state.top + ")");

	var selected = _track.selected;
	// Add background or border to track
	_track.element.select("rect.trackBackground")
		.attr("width", this.state.width)
		.attr("height", this.state.height)

	_track.updateSelected();

	_track.drawEditHandle();

	_track.drawAnnotationSymbols();
}

Track.prototype.editClicked = function() {
	const _track = this;
	if (_track.selected) {
		_track.selected = false;
		_track.parent.parent.stylePlot();
	} else {
		_track.selected = true;
		_track.parent.parent.styleTrack(this.key);
	}
}

Track.prototype.updateSelected = function(selected) {
	const _track = this;
	_track.selected = selected;
	_track.element.select("rect.trackBackground")
		.style("fill", function(){if (selected) {return "white"} else {return "white"}})
		.style("stroke", function(){if (selected) {return "blue"} else {return "white"}})

}

Track.prototype.style_schema = function() {
	const styles = [
		{name: "Filters", type: "section"},
		{name: "minimum feature length (bp)", type: "number", default: 0},
		{name: "k longest annotations", type: "number", default: 100},

		{name: "Arrows", type: "section"},
		{name: "show arrows based on strands", type: "bool", default: true},
		{name: "arrow style", type: "selection", default:"arrow at the end", options: ["arrow at the end","arrow in the middle","triangle"]},

		{name: "Rectangles", type: "section"},
		{name: "show rectangles", type: "bool", default: true},
		{name: "rectangle opacity", type: "range", default: 0.5, min: 0, max: 1, step: 0.05},

		{name: "Text", type: "section"},
		{name: "show names", type: "bool", default: false},
		{name: "font size", type: "range", default: 10, min: 0, max: 40, step: 2},
	];

	return styles;
}

Track.prototype.reset_styles = function() {
	const _track = this;
	var style_schema = _track.style_schema();
	_track.styles = {};
	for (var i in style_schema) {
		_track.styles[style_schema[i].name] = style_schema[i].default;
	}
}

Track.prototype.set_style = function(style,value) {
	const _track = this;
	_track.styles[style] = value;
	_track.element.selectAll('.annot').remove();
	_track.draw();
}

////////////////////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////////
//////////////////////////////////////////      Dot App       //////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////////


var DotApp = function(element, config) {

	this.element = element.style("display","flex");

	const frac = 0.30;
	const padding = 40;

	this.state = {
		ucscDb: "hg38",
		positions: [],
	}
	const plotWidth = config.width*(1-frac) - padding;
	const plotHeight = Math.min(plotWidth*0.80, config.height);

	this.mainLeft = this.element.append("div").attr("id", "mainLeft")
		.style("width", plotWidth + "px")
		.style("margin", "10px")
		.style("margin-right", padding + "px")

	this.plot_element = this.mainLeft.append("div").attr("id", "dotplot")
		.style("height", plotHeight + "px")
		.style("display", "inline-block");

	this.instructions = this.mainLeft.append("div")
		.style("margin-left", "20px")
		.style("margin-top", "20px")
		.style("margin-bottom", "20px")
		.style("text-align", "center");

	this.instructions.append("p").text("Click and drag to zoom in, double-click to zoom out.");

	this.instructions.append("p").attr("id", "annotMessage")
		.style("display", "none")
		.text("Showing up to 100 of the longest annotation features per track by default. Zoom in to see more details. To change this setting: hover on a track, click the pen icon, and edit the 'k longest annotations' number");
	
	
	this.inspectorArea = this.mainLeft.append("div").attr("id", "inspectorArea")
		.style("display", "none");
	this.inspectorArea.append("h3").text("Inspector");
	this.inspectorArea.append("p").text("Click on annotations to inspect them here:");
	this.inspector = this.inspectorArea.append("textarea")
		.text("")
		.attr("id","inspector")
		.style("width", "100%")
		.attr("rows", 10);


	this.linkOutArea = this.mainLeft.append("div").attr("id", "linkOutArea")
		.style("width", "100%");
	this.linkOutArea.append("label").attr("id","UcscDbLabel").text("UCSC reference database:");
	this.linkOutArea.append("input").attr("id","UcscDbInput")
		.property("value", this.state.ucscDb)
		.on("change", this.updateLinkValues.bind(this))


	this.dotplot = new DotPlot(this.plot_element, {parent: this, height: plotHeight, width: plotWidth});

	this.panel = this.element.append("div")
		.style("width", config.width * frac + "px")
		.style("vertical-align", "top")
		.style("display", "inline-block");

	this.action_panel = this.panel.append("div")
		.attr("id", "action_panel");

	this.action_panel.append("h4").text("Load all alignments in view from coordinate file")
	this.action_panel.append("button").attr("class", "load_unique").style("width", "100%").text("Load unique");
	this.action_panel.append("button").attr("class", "load_repetitive").style("width", "100%").text("Load repetitive");

	this.style_panel = this.panel.append("div")
		.attr("id","UI_container")
		.call(d3.superUI().object(this.dotplot));

	this.messageCallback = function(message, sentiment) {
		console.log(message);
	}

	if (typeof(config.messageCallback) === "function") {
		this.messageCallback = config.messageCallback;
	}
}


const memFormat = function(x) {
	return `${Math.round(x/10000)/100} MB`;
}

DotApp.prototype.showInInspector = function(text) {
	const old = this.inspector.property("value");
	this.inspector.property("value", old + "\n" + text);
}

DotApp.prototype.updateLinks = function() {

	const db = this.state.ucscDb;
	const positions = this.state.positions;
	const base = "https://genome.ucsc.edu/cgi-bin/hgTracks?db=";

	var links = [];
	for (var i = 0; i < positions.length; i++) {
		var d = positions[i]
		links.push({text: `UCSC (${db}): ${d.name}:${d.startBases}-${d.endBases}`, href: base + db + `&position=${d.name}:${d.startBases}-${d.endBases}`});
	}

	var linkElements = this.linkOutArea.selectAll("a").data(links);
	
	var newLinkElements = linkElements.enter().append("a");

	linkElements.exit().remove();
	
	linkElements.merge(newLinkElements)
		.style("display", "block")
		.attr("target", "_blank")
		.attr("href", function(d) {return d.href})
		.text(function(d) {return d.text});
}

DotApp.prototype.updateLinkValues = function() {
	this.state.ucscDb = this.linkOutArea.select("#UcscDbInput").property("value");

	this.updateLinks();
}

DotApp.prototype.updateLinkPositions = function(positions) {
	this.state.positions = positions;

	this.updateLinks();
}

DotApp.prototype.updateMemoryButtons = function(memUnique, memRepetitive) {
	var plot = this.dotplot;

	this.action_panel.select(".load_unique")
		.text(memUnique === 0 ? ("Unique: Fully loaded") : (`Load unique (${memFormat(memUnique)})`))
		.on("click", function() {plot.loadAllInView("unique")})
		.property("disabled", memUnique === 0);

	this.action_panel.select(".load_repetitive")
		.text(memRepetitive === 0 ? ("Repetitive: Fully loaded") : (`Load repetitive (${memFormat(memRepetitive)})`))
		.on("click", function() {plot.loadAllInView("repetitive")})
		.property("disabled", memRepetitive === 0);

}

DotApp.prototype.setData = function(data) {
	this.data = data;

	this.dotplot.setData(data);
}

DotApp.prototype.setCoords = function(coords, index) {
	this.coords = coords;
	this.index = index;

	this.dotplot.setCoords(coords, index);
}

DotApp.prototype.addAnnotationData = function(dataset) {
	this.dotplot.addAnnotationData(dataset);

	this.mainLeft.select("#inspectorArea").style("display", "block");
	this.mainLeft.select("#annotMessage").style("display", "block");
	
}

DotApp.prototype.styleTrack = function(trackKey) {
	var track = this.dotplot.state.trackGetter[trackKey];
	this.style_panel.call(d3.superUI().object(track));
	this.dotplot.updateTrackSelections(trackKey);
}

DotApp.prototype.stylePlot = function() {
	this.style_panel.call(d3.superUI().object(this.dotplot));
	this.dotplot.updateTrackSelections();
}
