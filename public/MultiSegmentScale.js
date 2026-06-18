var MultiSegmentScale = function(opts) {
	this.padding_fraction = Number(opts.padding_fraction) || 0; // as fraction of total domain length
	this.offset_dict = null;
	this.size_dict = null;
	this.total = null;
	this.hidden_scale = d3.scaleLinear().clamp(true);

	this.set_data(opts.data, opts.key_name, opts.length_name);
}

MultiSegmentScale.prototype.range = function(start_end_array) {
	this.hidden_scale.range(start_end_array);
}

MultiSegmentScale.prototype.set_data = function(data, key_name, length_name) {
	this.padding = this.padding_fraction*d3.sum(data, function(d) {return d[length_name]});
	if (isNaN(this.padding)) {
		console.error("MultiSegmentScale failed to get a numeric padding, perhaps padding_fraction was not set correctly:", this.padding_fraction);
	}
	this.total = 0;
	this.offset_dict = {};
	this.size_dict = {};
	for (var i = 0; i < data.length; i++) {
		var length = Number(data[i][length_name]);
		if (length === undefined || isNaN(length)) {
			console.error(length_name, "is not a key in", data[i]);
		}
		if (this.size_dict[String(data[i][key_name])] === undefined) {
			this.size_dict[String(data[i][key_name])] = length;
			this.offset_dict[String(data[i][key_name])] = this.total;
			this.total += length + this.padding;
		}
		if (isNaN(this.total)) {
			console.error("Total in MultiSegmentScale is not a number.");
		}
	}
	this.hidden_scale.domain([0,this.total]);
}

MultiSegmentScale.prototype.get = function(key, position) {
	var offset = this.offset_dict[String(key)];
	if (offset == undefined) {
		// console.log("Error, unrecognized key in MultiSegmentScale: " + String(key));
		return undefined;
	}
	if (position > this.size_dict[String(key)]) {
		return undefined;
	}
	return this.hidden_scale(offset + Number(position));

}

MultiSegmentScale.prototype.getBoundaries = function() {
	var boundaries = [];

	for (var key in this.offset_dict) {
		boundaries.push({
			name: key, 
			start: this.hidden_scale(this.offset_dict[key]), 
			end: this.hidden_scale(this.offset_dict[key]+this.size_dict[key]),
			length: this.size_dict[key],
		});
	}
	return boundaries;
}

MultiSegmentScale.prototype.contains = function(key,position) {
	var size = this.size_dict[String(key)];
	if (size == undefined) {
		return false;
	}
	if (Number(position) > size) {
		return false;
	}
	return true;
}
