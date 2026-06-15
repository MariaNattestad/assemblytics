(function() {
    let refs_selected = null;
    let queries_selected = null;
    let ref_index = null;
    let query_index = null;
    let coords_data = null;
    let ref_chrom_start_positions = {};
    let query_chrom_start_positions = {};
    let cumulative_ref_size = 0;
    let cumulative_query_size = 0;
    let svg = null;
    let dotplot_canvas = null;
    let dotplot_ref_scale = d3.scale.linear();
    let dotplot_query_scale = d3.scale.linear();
    let zoom = null;

    const max_num_alignments = 100000;
    const padding = { top: 20, right: 30, bottom: 80, left: 100 };

    window.initInteractiveDotplot = function(containerId, results) {
        const container = d3.select("#" + containerId);
        container.selectAll("*").remove();
        
        // Prepare data from results object
        const info = d3.csv.parse(new TextDecoder().decode(results.find(r => r.name.endsWith('.info.csv')).data));
        ref_index = d3.csv.parse(new TextDecoder().decode(results.find(r => r.name.endsWith('.ref.index')).data));
        query_index = d3.csv.parse(new TextDecoder().decode(results.find(r => r.name.endsWith('.query.index')).data));
        coords_data = d3.csv.parse(new TextDecoder().decode(results.find(r => r.name.endsWith('.oriented_coords.csv')).data));

        if (coords_data.length > max_num_alignments) coords_data = coords_data.slice(0, max_num_alignments);

        // Process indices
        cumulative_ref_size = 0;
        ref_index.forEach(d => {
            ref_chrom_start_positions[d.ref] = cumulative_ref_size;
            cumulative_ref_size += +d.ref_length;
        });

        cumulative_query_size = 0;
        query_index.forEach(d => {
            query_chrom_start_positions[d.query] = cumulative_query_size;
            cumulative_query_size += +d.query_length;
        });

        const width = container.node().getBoundingClientRect().width || 800;
        const height = 600;

        dotplot_ref_scale.domain([0, cumulative_ref_size]).range([0, width - padding.left - padding.right]);
        dotplot_query_scale.domain([0, cumulative_query_size]).range([height - padding.top - padding.bottom, 0]);

        svg = container.append("svg")
            .attr("width", width)
            .attr("height", height)
            .append("g")
            .attr("transform", `translate(${padding.left},${padding.top})`);

        // Background
        svg.append("rect")
            .attr("width", width - padding.left - padding.right)
            .attr("height", height - padding.top - padding.bottom)
            .attr("fill", "#fff")
            .attr("stroke", "#ccc");

        dotplot_canvas = svg.append("g")
            .attr("clip-path", "url(#clip)");

        svg.append("defs").append("clipPath")
            .attr("id", "clip")
            .append("rect")
            .attr("width", width - padding.left - padding.right)
            .attr("height", height - padding.top - padding.bottom);

        const draw = () => {
            const lines = dotplot_canvas.selectAll(".alignment")
                .data(coords_data);

            lines.enter().append("line")
                .attr("class", "alignment")
                .attr("stroke-width", 1.5);

            lines
                .attr("x1", d => dotplot_ref_scale(ref_chrom_start_positions[d.ref] + (+d.ref_start)))
                .attr("x2", d => dotplot_ref_scale(ref_chrom_start_positions[d.ref] + (+d.ref_end)))
                .attr("y1", d => dotplot_query_scale(query_chrom_start_positions[d.query] + (+d.query_start)))
                .attr("y2", d => dotplot_query_scale(query_chrom_start_positions[d.query] + (+d.query_end)))
                .attr("stroke", d => d.tag === "unique" ? "black" : "red");

            lines.exit().remove();
        };

        zoom = d3.behavior.zoom()
            .x(dotplot_ref_scale)
            .y(dotplot_query_scale)
            .on("zoom", draw);

        svg.append("rect")
            .attr("class", "overlay")
            .attr("width", width - padding.left - padding.right)
            .attr("height", height - padding.top - padding.bottom)
            .attr("fill", "none")
            .attr("pointer-events", "all")
            .call(zoom);

        draw();

        // Add axes labels (simplified for PoC)
        svg.append("text")
            .attr("text-anchor", "middle")
            .attr("x", (width - padding.left - padding.right) / 2)
            .attr("y", height - padding.bottom + 40)
            .text("Reference Position (bp)");

        svg.append("text")
            .attr("text-anchor", "middle")
            .attr("transform", "rotate(-90)")
            .attr("y", -padding.left + 40)
            .attr("x", -(height - padding.top - padding.bottom) / 2)
            .text("Query Position (bp)");
    };
})();
