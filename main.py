import json
from pathlib import Path
from typing import Dict, Optional
import tempfile
import os

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

from data_models import Graph
from get_smart_title import get_smart_title


def load_graph_from_jsonl(jsonl_path: str) -> Optional[Graph]:
    """
    Load the final graph from a JSONL log file.

    Looks for SystemFinishEvent first, then falls back to the last GraphMergeEvent.
    """
    graph = None

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            try:
                event = json.loads(line)
                event_type = event.get("event")
                data = event.get("data", {})

                if event_type == "SystemFinishEvent":
                    graph_data = data.get("graph", {})
                    if graph_data:
                        graph = Graph(**graph_data)
                        break

                elif event_type == "GraphMergeEvent":
                    graph_data = data.get("graph", {})
                    if graph_data:
                        graph = Graph(**graph_data)

            except (json.JSONDecodeError, KeyError, TypeError) as e:
                st.warning(f"Skipping malformed line: {e}")
                continue

    return graph


def calculate_node_levels(graph: Graph) -> Dict[str, int]:
    """
    Calculate the depth/level of each node in the graph.
    Root nodes (no premises) are at level 0.
    Children are at level = max(parent levels) + 1.

    Returns:
        Dictionary mapping node_id to its level
    """
    levels = {}

    def get_level(node_id: str) -> int:
        """Recursively calculate the level of a node."""
        if node_id in levels:
            return levels[node_id]

        if node_id not in graph.nodes:
            return 0

        node = graph.nodes[node_id]
        if not node.premises:
            # Root node
            levels[node_id] = 0
            return 0

        # Level is max of all parent levels + 1
        parent_levels = [get_level(pid) for pid in node.premises if pid in graph.nodes]
        if parent_levels:
            level = max(parent_levels) + 1
        else:
            level = 0

        levels[node_id] = level
        return level

    # Calculate levels for all nodes
    for node_id in graph.nodes:
        get_level(node_id)

    return levels


def create_pyvis_network(
    graph: Graph,
    height: str = "800px",
    width: str = "100%",
    physics: bool = True,
    node_size: int = 25,
) -> Network:
    """
    Create a Pyvis network visualization of the reasoning graph.

    Args:
        graph: The Graph object to visualize
        height: Height of the visualization
        width: Width of the visualization
        physics: Whether to enable physics simulation
        node_size: Base size for nodes
    """
    # Create network
    net = Network(
        height=height, width=width, bgcolor="#ffffff", font_color="black", directed=True
    )

    # Calculate node levels for hierarchical layout
    node_levels = calculate_node_levels(graph)

    # Configure physics
    if physics:
        net.barnes_hut(
            gravity=-2000,
            central_gravity=0.1,
            spring_length=250,  # Reduced to decrease spacing between nodes
            spring_strength=0.05,
            damping=0.09,
        )
    else:
        net.toggle_physics(False)

    # Find root nodes (nodes with no premises)
    root_nodes = {node_id for node_id, node in graph.nodes.items() if not node.premises}

    # Color scheme
    normal_color = "#ADD8E6"  # lightblue
    refutation_color = "#F08080"  # lightcoral
    root_color = "#90EE90"  # lightgreen

    # Add nodes
    for node_id, node in graph.nodes.items():
        # Determine node color
        if node.is_refutation:
            color = refutation_color
            border_color = "#DC143C"  # crimson
        elif node_id in root_nodes:
            color = root_color
            border_color = "#228B22"  # forestgreen
        else:
            color = normal_color
            border_color = "#4682B4"  # steelblue

        # Format label - include reference count indicator
        conclusion = get_smart_title(node.conclusion, max_words_per_line=8, max_lines=2)
        label = f"{node.id}\n{conclusion}"
        # if node.references:
        #     label += f"\n[{len(node.references)} ref{'s' if len(node.references) > 1 else ''}]"

        # Create tooltip with full information including references
        tooltip = f"ID: {node.id}\n\nConclusion: {get_smart_title(node.conclusion, max_words_per_line=12, max_lines=8)}\n\nJustification: {get_smart_title(node.justification, max_words_per_line=12, max_lines=8)}"

        # Add reference details to tooltip
        if node.references:
            tooltip += f"\n\n--- References ({len(node.references)}) ---"
            for ref_id in node.references:
                if ref_id in graph.references:
                    ref = graph.references[ref_id]
                    # tooltip += f"\n\n[{ref_id[:8]}...]"
                    # tooltip += f"\nTitle: {ref.source_citation.title}"
                    # tooltip += f"\n**Authors:** {', '.join(ref.source_citation.authors)}"
                    # tooltip += f"\nStatement: {get_smart_title(ref.statement, max_words_per_line=8, max_lines=100)}"
                    # if ref.context:
                    #     tooltip += f"\nContext: {get_smart_title(ref.context, max_words_per_line=8, max_lines=100)}"
                    tooltip += f"\n\n[{ref_id[:8]}] "
                    tooltip += f"{ref.source_citation.title}"
                    if len(ref.source_citation.authors) >= 2:
                        tooltip += f" (by {', '.join(ref.source_citation.authors[:-1])} et al.)"
                    elif len(ref.source_citation.authors) == 1:
                        tooltip += f" (by {ref.source_citation.authors[0]})"
                    tooltip += f"\n{get_smart_title(ref.statement, max_words_per_line=10, max_lines=1)}"

        if node.is_refutation:
            tooltip += "\n\n[REFUTATION]"

        # Calculate node size based on number of references
        size = node_size + (len(node.references) * 100)

        # Get the level for this node (for hierarchical layout)
        level = node_levels.get(node_id, 0)

        net.add_node(
            node_id,
            label=label,
            title=tooltip,
            color=color,
            size=size,
            borderWidth=2,
            borderWidthSelected=4,
            shape="box",
            font={"size": 16, "face": "Arial"},
            border=border_color,
            level=level,  # Set level for hierarchical layout
        )

    # Add edges (premise relationships)
    for node_id, node in graph.nodes.items():
        for premise_id in node.premises:
            if premise_id in graph.nodes:
                net.add_edge(
                    premise_id,
                    node_id,
                    color={"color": "#666666"},
                    width=2,
                    arrows="to",
                )
            # else:
            #     # Premise not found - add as a warning node
            #     net.add_node(
            #         premise_id,
            #         label=f"{premise_id}\n[MISSING]",
            #         color='#FFFF00',  # yellow
            #         size=node_size,
            #         shape='box',
            #         borderWidth=2,
            #         borderWidthSelected=4,
            #         border='#FF0000',  # red
            #         font={'color': '#FF0000'}
            #     )
            #     net.add_edge(
            #         premise_id,
            #         node_id,
            #         color={'color': '#FF0000'},
            #         width=2,
            #         style='dashed',
            #         arrows='to'
            #     )

    # Set options for better visualization with hierarchical layout
    net.set_options("""
    var options = {
      "layout": {
        "hierarchical": {
          "enabled": true,
          "direction": "UD",
          "sortMethod": "directed",
          "levelSeparation": 125,
          "nodeSpacing": 100,
          "treeSpacing": 100,
          "blockShifting": true,
          "edgeMinimization": true,
          "parentCentralization": true,
          "shakeTowards": "leaves"
        }
      },
      "nodes": {
        "borderWidth": 2,
        "borderWidthSelected": 4,
        "font": {
          "size": 12,
          "face": "Arial"
        }
      },
      "edges": {
        "color": {
          "inherit": true
        },
        "smooth": {
          "enabled": true,
          "type": "continuous",
          "roundness": 0.5
        },
        "arrows": {
          "to": {
            "enabled": true,
            "scaleFactor": 1.2
          }
        }
      },
      "interaction": {
        "hover": false,
        "tooltipDelay": 100,
        "zoomView": true,
        "dragView": true
      },
      "physics": {
        "enabled": false,
        "stabilization": {
          "enabled": true,
          "iterations": 200
        }
      }
    }
    """)

    return net


def main():
    """Main Streamlit app entry point."""
    st.set_page_config(
        page_title="Graph Reasoning Visualizer", page_icon="📊", layout="wide"
    )

    st.title("📊 Graph Reasoning Visualizer")
    st.markdown("Visualize reasoning graphs from JSONL log files")

    # Sidebar for file upload and settings
    with st.sidebar:
        st.header("📁 Load Graph")

        # File upload
        uploaded_file = st.file_uploader(
            "Upload JSONL file",
            type=["jsonl"],
            help="Upload a JSONL log file containing graph data",
        )

        # Or choose from example files or specify file path
        st.markdown("---")
        st.subheader("Or choose an example file")

        # Directory containing example files (relative to this script)
        example_dir = Path(__file__).parent / "example-graphs"
        example_options = ["(none)"]
        if example_dir.exists() and example_dir.is_dir():
            # List only .jsonl files
            for p in sorted(example_dir.iterdir()):
                if p.is_file() and p.suffix.lower() == ".jsonl":
                    example_options.append(p.name)

        selected_example = st.selectbox(
            "Choose an example JSONL file",
            example_options,
            index=0,
            help="Select a JSONL file shipped in the `example-graphs` folder",
        )

        # Determine which source to use
        tmp_path = None
        if uploaded_file is not None:
            # Save uploaded file to temp location
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".jsonl", mode="w"
            ) as tmp_file:
                tmp_file.write(uploaded_file.getvalue().decode("utf-8"))
                tmp_path = tmp_file.name
            file_to_load = tmp_path
            file_source = "uploaded"
        elif selected_example and selected_example != "(none)":
            # Use the selected example file from the example-graphs folder
            candidate = example_dir / selected_example
            if candidate.exists():
                file_to_load = str(candidate)
                file_source = "example"
            else:
                file_to_load = None
                file_source = None
        else:
            file_to_load = None
            file_source = None

        st.markdown("---")
        st.header("⚙️ Visualization Settings")

        # Visualization options
        height = st.slider("Graph Height", 400, 1200, 800, 50)
        physics = st.checkbox("Enable Physics", value=True)
        node_size = st.slider("Node Size", 10, 50, 25, 2)

    # Main content area
    if file_to_load is None:
        st.info(
            "👈 Please choose a file in the sidebar to get started, or upload your own."
        )
        st.markdown("""
        ### How to use:
        1. Upload a JSONL file using the file uploader, or
        2. Chose an example file.
        3. Adjust visualization settings in the sidebar
        """)
        return

    # Load graph
    with st.spinner(f"Loading graph from {file_source} file..."):
        try:
            graph = load_graph_from_jsonl(file_to_load)
            # Clean up temp file immediately after loading if it was uploaded
            if file_source == "uploaded" and tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        except Exception as e:
            st.error(f"Error loading graph: {e}")
            # Clean up temp file even on error
            if file_source == "uploaded" and tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
            return

    if graph is None:
        st.error("Could not find graph data in the JSONL file.")
        st.info("Looking for SystemFinishEvent or GraphMergeEvent with graph data.")
        return

    # Display graph statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Nodes", len(graph.nodes))
    with col2:
        st.metric("References", len(graph.references))
    with col3:
        root_nodes = sum(1 for node in graph.nodes.values() if not node.premises)
        st.metric("Root Nodes", root_nodes)

    # Create and display Pyvis network
    st.markdown("---")
    st.subheader("Interactive Graph Visualization")

    st.info("💡 Tip: Drag nodes, scroll to zoom, and hover for detailed information!")

    with st.spinner("Generating visualization..."):
        net = create_pyvis_network(
            graph, height=f"{height}px", physics=physics, node_size=node_size
        )

        # Generate HTML and display
        html = net.generate_html()
        components.html(html, height=height + 50)


if __name__ == "__main__":
    main()
