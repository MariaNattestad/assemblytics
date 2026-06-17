d3.superUI = function() {
	var my_object = undefined;

	var style_schema = undefined;
	var element = null;

	// my(selection) executes when we do .call() on a d3 selection:
	function my(selection) {
		selection.each(function(d, i) {
			element = d3.select(this);
			my.create_table();
		});
	};

	my.create_table = function() {

		element.html("");
		var table = element.append("table").attr("class","d3-superUI-table");

		style_schema = my_object.style_schema();
		
		table.append("tr").attr("class","d3-superUI-header-row").selectAll("th").data(["Style","Set","Reset"]).enter().append("th").text(function(d){return d});

		var rows = table.selectAll("tr.d3-superUI-row").data(style_schema).enter().append("tr").attr("class","d3-superUI-row");
		rows.filter(function(d) {return d.type !== "colorscale" && d.type !== "section"})
			.append("td").attr("class","superUI-variable").html(function(d) {return d.name + ":"});

		// Numbers
		rows.filter(function(d) {return d.type=="number"})
			.append("td").attr("class","superUI-value")
				.append("input")
					.attr("type","number")
					.property("value",my.current_style)
					.on("change",function(d) {
						my_object.set_style(d.name,Number(this.value));
					})
					.each(function(d) {
						var at = ["min","max","step"];
						for (var i in at) {
							if (d[at[i]] != undefined) {
								d3.select(this).attr(at[i],d[at[i]]);
							}
						}
					});

		// Strings
		rows.filter(function(d) {return d.type=="string"})
			.append("td").attr("class","superUI-value")
				.append("input")
					.attr("type","text")
					.property("value",my.current_style)
					.on("change",function(d) {
						my_object.set_style(d.name,this.value);
					})

		// Ranges
		rows.filter(function(d) {return d.type=="range"})
			.append("td").attr("class","superUI-value")
				.append("input")
					.attr("type","range")
					.property("value",my.current_style)
					.attr("min",function(d) {return d.min})
					.attr("max",function(d) {return d.max})
					.attr("step",function(d) {return d.step})
					.on("change",function(d) {
						my_object.set_style(d.name,Number(this.value));
					})

		// Percentages
		rows.filter(function(d) {return d.type=="percentage"})
			.append("td").attr("class","superUI-value percentage")
				.append("input")
					.attr("type","number")
					.property("value",my.current_style)
					.attr("min",function(d) {return d.min*100})
					.attr("max",function(d) {return d.max*100})
					.attr("step",function(d) {return d.step*100})
					.on("change",function(d) {
						if (this.value > 100) {
							this.value = 100;
						}
						if (this.value < 0) {
							this.value = 0;
						}
						my_object.set_style(d.name,Number(this.value)/100);
					});

		// Booleans
		rows.filter(function(d) {return d.type=="bool"})
			.append("td").attr("class","superUI-value")
				.append("input")
					.attr("type","checkbox")
					.property("checked", my.current_style)
					.on("change",function(d) {
						my_object.set_style(d.name,this.checked);
					});

		// Colors
		rows.filter(function(d) {return d.type=="color"})
			.append("td").attr("class","superUI-value")
				.append("input")
					.attr("type","color")
					.property("value",my.current_style)
					.on("change",function(d) {
							my_object.set_style(d.name,this.value);
						});
		// Colorscales
		var colorscales = rows.filter(function(d) {return d.type == "colorscale"})
			.append("td").attr("colspan","3");

		colorscales.each(function(d) {
			d3.select(this).call(
				d3.superColorScaleUI().object(my_object).scale_schema(d)
			)
		});

		// Section headers
		rows.filter(function(d) {return d.type=="section"})
			.append("th")
				.attr("class","superUI-section-header")
				.attr("colspan","3")
				.html(function(d) {return d.name});


		// Selections
		var selector = rows.filter(function(d) {return d.type=="selection"})
			.append("td").attr("class","superUI-value")
			.append("select").attr("class","form-control");

		selector.selectAll("option.set").data(function(d) {return d.options}).enter()
			.append("option")
				.attr("class","set")
				.text(function(d,i){return d})
				.property("value",function(d,i){return d});

		selector.on('change', function(d) {
			var index = this.options[this.selectedIndex].value;
			if (index !== -1) {
				my_object.set_style(d.name,this.value);
			}
		});

		// DEFAULTS
		rows.append("td").attr("class","superUI-default")
			.filter(function(d) {return d.type !== "colorscale" && d.type !== "section"})
				.append("button")
					.html(my.show_default)
					.attr("class","btn btn-xs btn-default")
					.on("click", function(d) {
						my_object.set_style(d.name, d.default);
						my.update_values(d.name);
					});


		// Apply initial values:
		style_schema.map(function(d) {my.update_values(d.name)});

	};

	my.show_default = function(d) {
		if (d.type == "colorscale") {
			return "default";
		}
		if (d.type == "number") {
			if (d.default > 1000000 || d.default < -1000000) {
				return Math.round(d.default/1000000) + " M";
			} else {
				return Number(Math.round(d.default+'e'+2)+'e-'+2);
			}
		}
		if (d.type == "percentage") {
			return Number(Math.round(d.default*100.0+'e'+2)+'e-'+2) + "%";
		}
		
		return d.default;
	}
	my.update_values = function(style) {
		element.selectAll("td.superUI-value input")
			.filter(function(d) {return d.name==style && d.type != "color"})
				.property("value",my.current_style);

		element.selectAll("td.superUI-value textarea")
			.filter(function(d) {return d.name==style})
			.property("value",my.current_style);

		element.selectAll("td.superUI-value input")
			.filter(function(d) {return d.name==style && d.type != "checkbox"})
				.property("checked",my.current_style);

		element.selectAll("td.superUI-value select")
			.filter(function(d) {return d.name==style})
				.selectAll("option.set").property("selected", function(d, i) {
					return d===my.current_style({name: style})
				});
	}

	my.current_style = function(d, i) {
		var style = my_object.styles[d.name];
		if (d.type == "color") {
			if (style == "black") {
				return "#000000";
			}
			if (style == "white") {
				return "#ffffff";
			}
		}
		
		if (d.type == "percentage") {
			return style*100.0;
		}
		return style;
	}
	
	my.object = function(value) {
		// if (!arguments.length) return my_object;
		my_object = value;
		
		// Check that proper functions exist for the object this was called on:
		if (typeof(my_object.style_schema) !== "function") { throw "d3.superUI can only be called with an object that has a function called 'style_schema'";}
		if (typeof(my_object.set_style) !== "function") { throw "d3.superUI can only be called with an object that has a function called 'set_style'";}
		if (typeof(my_object.styles) !== "object") { throw "d3.superUI can only be called with an object that has a property called 'styles'";}

		return my;
	};

	return my;
}

d3.superColorScaleUI = function() {
	var my_object = undefined;
	var my_scale_schema = undefined;
	var current_colors = undefined;
	var element = null;

	// my(selection) executes when we do .call() on a d3 selection:
	function my(selection) {
		selection.each(function(d, i) {
			element = d3.select(this);
			my_scale_schema = d;
			current_colors = my.get_current_colors();
			my.create_table();
		});
	};

	my.create_table = function() {
		element.attr("class","superColorScaleUI").append("label").html(my_scale_schema.name);

		var ID = my_scale_schema.name.replace(/ /g,"_");
		
		// Tabs
		var choices = element.append("ul").attr("class", "nav nav-tabs").selectAll("li")
			.data([{name:"set", title:"choose set"}, {name:"pick", title:"pick colors"},{name:"write", title:"write list"}])
			.enter().append("li");
		choices.filter(function(d) {return d.name == "set"}).classed("active",true);
		
		choices.append("a").attr("data-toggle","tab")
					.attr("href",function(d) {return "#" + ID + "_" + d.name})
					.html(function(d) {return d.title});

		var tabs = element.append("div").attr("class","tab-content");

		// Dropdown
		var selector = tabs.append("div").attr("id",ID + "_" + "set").attr("class","tab-pane fade in active")
			.style("padding","2vmin 2vmin 2vmin 2vmin")
			.append("select").attr("class","form-control");
		
		selector.append("option").attr("class","custom_set").property("disabled",true).property("value",-1).text("-- custom --");

		selector.selectAll("option.set").data(my_scale_schema.dropdown_options).enter()
			.append("option")
				.attr("class","set")
				.text(function(d,i){return d.name})
				.property("value",function(d,i){return i})
				.property("selected",function(d,i){return i===0});

		selector.on('change', function() {
			var index = this.options[this.selectedIndex].value;
			if (index !== -1) {
				current_colors = array_deep_copy(my_scale_schema.dropdown_options[index].colors);
				set_colorscale();
			} else {
				console.log("Custom");
			}
		})

		// Table of color pickers
		var color_rows = tabs.append("div").attr("id",ID + "_" + "pick").attr("class","tab-pane fade")
			.append("div").selectAll("div.color_element").data(my_scale_schema.domain).enter().append("div").attr("class","color_element");

		color_rows.append("span").text(function(d,i) {return d});
		color_rows.append("input").attr("type","color")
			.on('change',function(d,i) {
				set_one_color(i,this.value);
			});

		// Text area
		tabs.append("div").attr("id",ID + "_" + "write").attr("class","tab-pane fade")
			.append("textarea")
				.style("width","100%")
				.attr("rows",5)
				.on("change", function() {
					current_colors = this.value.split(",");
					set_colorscale();
					set_dropdown_to_custom();
				});

		function set_one_color(index, new_value) {
			current_colors[index] = new_value;
			set_colorscale();
			set_dropdown_to_custom();
		}
		function set_dropdown_to_custom() {
			selector.select(".custom_set").property("selected",true);
		}
		function array_deep_copy(a) {
			var b = [];
			for (var i in a) {
				b.push(a[i]);
			}
			return b;
		}
		function fill_out_colors() {
			var scale_length = current_colors.length;
			for (var i in my_scale_schema.domain) {
				if (current_colors[i] === undefined) {
					current_colors.push(current_colors[i % scale_length]);
				}
			}
		}
		function set_colorscale() {
			fill_out_colors();
			my_object.set_style(my_scale_schema.name, current_colors);
			refresh_UI();
		}
		
		function refresh_UI() {
			console.log("refreshing colorscale in UI elements");
			element.selectAll("textarea").property("value",current_colors);
			
			color_rows.select("input").property("value",function(d,i) {return current_colors[i % current_colors.length]});
		}

		refresh_UI();
	}

	my.get_current_colors = function() {
		return my_object.styles[my_scale_schema.name];
	}

	my.object = function(value) {
		my_object = value;
		
		// Check that proper functions exist for the object this was called on:
		if (typeof(my_object.style_schema) !== "function") { throw "d3.superUI can only be called with an object that has a function called 'style_schema'";}
		if (typeof(my_object.set_style) !== "function") { throw "d3.superUI can only be called with an object that has a function called 'set_style'";}
		if (typeof(my_object.styles) !== "object") { throw "d3.superUI can only be called with an object that has a property called 'styles'";}

		return my;
	};

	my.scale_schema = function(value) {
		my_scale_schema = value;
		if (my_scale_schema.domain === undefined) { throw "domain is undefined for color scale in style schema";}
		return my;
	}

	return my;
}