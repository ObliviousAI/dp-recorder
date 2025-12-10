import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
import numpy as np
import pandas as pd
from typing import Optional, Tuple, Any
from graphviz import Digraph

from dp_mechanisms.auditing.audit_primitives import Auditor


def _summarize_val(val: Any) -> str:
    """Helper to make data payloads human-readable in graphs."""
    if val is None:
        return "None"
    
    # Handle Numpy
    if isinstance(val, np.ndarray):
        shape_str = f"{list(val.shape)}"
        if val.size == 0: return f"Empty Array {shape_str}"
        if val.size < 5: return f"{val} {shape_str}"
        return f"Array {shape_str} | μ={val.mean():.3g}"
    
    # Handle Torch
    if hasattr(val, 'shape') and hasattr(val, 'device'): # simplistic torch check
        shape_str = f"{list(val.shape)}"
        try:
            mean_val = val.float().mean().item()
            return f"Tensor {shape_str} | μ={mean_val:.3g}"
        except:
            return f"Tensor {shape_str}"

    # Handle primitives
    if isinstance(val, (int, float)):
        return f"{val:.4g}"
    
    # Handle containers
    if isinstance(val, (list, tuple)):
        return f"List/Tuple (len={len(val)})"
    
    return str(type(val).__name__)

def _extract_params_str(params: dict) -> str:
    """Extracts key DP parameters for the header."""
    if not params: return ""
    keys = ['epsilon', 'delta', 'noise_multiplier', 'sigma', 'l2_norm_clip', 'max_grad_norm']
    found = []
    for k, v in params.items():
        if k in keys:
            symbol = k
            if k == 'epsilon': symbol = 'ε'
            elif k == 'delta': symbol = 'δ'
            elif k in ['noise_multiplier', 'sigma']: symbol = 'σ'
            found.append(f"{symbol}={v}")
    return ", ".join(found)

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from graphviz import Digraph
from typing import Optional, Any

def render_flow_graph(rec: 'Auditor', out_path: Optional[str] = None, *, format: str = 'png', title: Optional[str] = None) -> str:
    """
    Generates a flowchart that visualizes partial/failed replays.
    
    States:
    1. Replayed (Green): Successfully verified.
    2. Crash/Fail (Red): The exact step where replay stopped/invariant failed.
    3. Pending (Grey): Steps recorded in D but not reached in D' replay.
    """
    dot = Digraph(comment='DP Mechanism Flow', format=format)
    dot.attr(rankdir='LR') 
    dot.attr('node', fontname='Helvetica') 
    
    if title:
        dot.attr(label=title, labelloc='t', fontsize='20')

    prev_node_id = 'start'
    
    # Start Node
    dot.node('start', label='Input\n(D / D\')', shape='circle', style='filled', fillcolor='#e9ecef', fontsize='10')

    # The cursor indicates the next expected step. 
    # If the replay crashed, the cursor points to the failed step (or the one that wasn't completed).
    crash_point = rec._cursor
    
    for i, entry in enumerate(rec.log):
        node_id = f"node_{i}"
        
        # --- Determine State ---
        is_replayed = i < crash_point
        is_crash_site = (i == crash_point) and (rec.mode == 'replay' or rec.mode == rec.mode.REPLAY)
        is_pending = i > crash_point

        # Defaults for "Pending"
        fill_color = "#f8f9fa" # Very light grey
        border_color = "#aaaaaa" # Grey
        style = "dashed"
        font_color = "#aaaaaa"
        
        if is_replayed:
            style = "solid"
            font_color = "black"
        elif is_crash_site:
            style = "bold"
            font_color = "black"

        # --- 1. Invariants (Check Equality) ---
        if entry.kind == "EQ":
            label_text = f"Invariant #{i}\n{entry.label}"
            
            if is_replayed:
                # Passed
                shape_color = "#d4edda" # Light Green
                border_color = "#28a745"
            elif is_crash_site:
                # FAILED
                shape_color = "#f8d7da" # Light Red
                border_color = "#dc3545"
                label_text += "\n(FAILED HERE)"
            else:
                # Pending
                shape_color = "#f0f0f0"
                border_color = "#cccccc"
                label_text += "\n(Pending)"

            dot.node(node_id, 
                     label=label_text, 
                     shape='diamond', 
                     style='filled' if not is_pending else 'dashed,filled', 
                     fillcolor=shape_color, 
                     color=border_color,
                     fontcolor=font_color,
                     fontsize='10',
                     height='0.8')
            
            edge_style = 'dashed' if is_pending else 'solid'
            dot.edge(prev_node_id, node_id, style=edge_style, color=border_color)
            prev_node_id = node_id
            continue

        # --- 2. Mechanisms ---
        
        # A. Header
        param_str = _extract_params_str(entry.params)
        header_text = f"<b>#{i} {entry.kind}</b>"
        if param_str:
            header_text += f"<br/><font point-size='10' color='{font_color}'>[{param_str}]</font>"

        # B. Inputs
        # Check if we actually have data for D' (only if replayed)
        val_d = list(entry.inputs_d.values())[0] if entry.inputs_d else None
        val_dp = list(entry.inputs_dp.values())[0] if (entry.inputs_dp and is_replayed) else None

        row_d = f"<TR><TD ALIGN='LEFT'><b>D:</b> {_summarize_val(val_d)}</TD></TR>"
        
        if is_replayed:
             row_dp = f"<TR><TD ALIGN='LEFT'><b>D':</b> {_summarize_val(val_dp)}</TD></TR>"
        elif is_crash_site:
             # If it crashed HERE, we might or might not have input depending on where exactly it crashed.
             # Usually, if it crashed on an invariant *before* this, we wouldn't be here. 
             # If it crashed *inside* this mechanism, we assume input was provided but execution failed.
             row_dp = "<TR><TD ALIGN='LEFT' BGCOLOR='#fff3cd'><b>D':</b> (Execution Halting)</TD></TR>"
        else:
             row_dp = "<TR><TD ALIGN='LEFT'><font color='#aaaaaa'><i>D': (Pending)</i></font></TD></TR>"

        # C. Footer (Sensitivity Check)
        footer_text = "Status: Recorded"
        footer_bg = "#e2e3e5"
        
        if is_replayed and entry.inputs_dp:
            # Logic for completed steps
            try:
                if not isinstance(val_d, np.ndarray):
                    val_d = np.array(val_d)
                if not isinstance(val_dp, np.ndarray):
                    val_dp = np.array(val_dp)
                if isinstance(val_d, np.ndarray) and val_d.ndim == 0:
                    val_d = val_d.reshape(1)
                if isinstance(val_dp, np.ndarray) and val_dp.ndim == 0:
                    val_dp = val_dp.reshape(1)
                dist = entry.metric_fn(val_d, val_dp)
                limit = entry.sensitivity_val
                if dist <= limit + 1e-9:
                    footer_bg = "#d4edda"
                    border_color = "#28a745"
                    footer_text = f"Δ: {dist:.4f} ≤ Sens: {limit}<br/><B>✓ OK</B>"
                else:
                    footer_bg = "#f8d7da"
                    border_color = "#dc3545"
                    footer_text = f"Δ: {dist:.4f} > Sens: {limit}<br/><B>✘ VIOLATION</B>"
            except:
                footer_text = "Metric Error"
        
        elif is_crash_site:
            footer_bg = "#f8d7da"
            border_color = "#dc3545"
            footer_text = "<B>⛔ CRASH / STOP</B>"
        
        elif is_pending:
            footer_bg = "#f0f0f0"
            border_color = "#cccccc"
            footer_text = "..."

        # HTML Table Construction
        label_html = f"""<
        <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">
            <TR><TD BGCOLOR="#ffffff" BORDER="1" COLOR="{border_color}">{header_text}</TD></TR>
            {row_d}
            {row_dp}
            <TR><TD BGCOLOR="{footer_bg}" BORDER="1" COLOR="{border_color}">{footer_text}</TD></TR>
        </TABLE>>"""

        dot.node(node_id, label=label_html, shape='plain')
        
        edge_style = 'dashed' if is_pending else 'solid'
        dot.edge(prev_node_id, node_id, style=edge_style, color=border_color)
        prev_node_id = node_id

    # End Node (Ghosted if not reached)
    end_style = 'filled' if rec._cursor >= len(rec.log) else 'dashed,filled'
    dot.node('end', label='Output', shape='circle', style=end_style, fillcolor='#e9ecef', fontsize='10')
    dot.edge(prev_node_id, 'end', style='dashed' if rec._cursor < len(rec.log) else 'solid')

    if out_path:
        return dot.render(out_path, cleanup=True)
    
    return dot.source


def plot_call_diffs(rec: 'Auditor', *, save_path: Optional[str] = None, show: bool = False, figsize: Tuple[int, int] = (12, 5)) -> Optional[str]:
    """
    Plots a 'Sensitivity Timeline'.
    
    X-Axis: Sequence of mechanism calls.
    Y-Axis: The measured distance between D and D' inputs.
    
    Features:
    - Visualizes the 'Budget' (Allowed Sensitivity) vs 'Cost' (Actual Distance).
    - Highlights violations in Red.
    """
    # Filter for only mechanism entries that have neighbor data
    data = []
    for i, entry in enumerate(rec.log):
        if entry.kind == "EQ": continue
        if entry.inputs_dp is None: continue # Skip if no replay
        
        try:
            val_d = list(entry.inputs_d.values())[0]
            val_dp = list(entry.inputs_dp.values())[0]
            dist = entry.metric_fn(val_d, val_dp)
            
            data.append({
                "Call ID": i,
                "Mechanism": f"#{i}\n{entry.kind}",
                "Distance": dist,
                "Sensitivity Limit": entry.sensitivity_val,
                "Violation": dist > (entry.sensitivity_val + 1e-9)
            })
        except Exception:
            continue

    if not data:
        print("[Plot Warning] No valid comparison data found. Did you run auditor.set_replay()?")
        return None

    df = pd.DataFrame(data)

    # Setup Plot
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=figsize)

    # 1. Plot the "Allowed Limit" (Sensitivity) as a step line or bars
    # We use bars with low opacity to represent the "Safe Zone"
    ax.bar(df["Mechanism"], df["Sensitivity Limit"], color='gray', alpha=0.2, label='Allowed Sensitivity (Limit)', width=0.6)

    # 2. Plot the "Actual Distance" as a stem plot or points
    # We iterate to color code violations
    for idx, row in df.iterrows():
        x = idx
        y = row["Distance"]
        color = '#d62728' if row["Violation"] else '#2ca02c' # Red if fail, Green if pass
        marker = 'X' if row["Violation"] else 'o'
        
        # Draw the stem line
        ax.vlines(x=idx, ymin=0, ymax=y, color=color, linewidth=2)
        # Draw the marker
        ax.plot(idx, y, marker=marker, color=color, markersize=10, zorder=10)

    # Formatting
    ax.set_ylabel("Input Distance metric(D, D')")
    ax.set_xlabel("Mechanism Call Sequence")
    ax.set_title("Sensitivity Compliance Audit", fontsize=14, fontweight='bold')
    
    # Add legend manually to handle the custom coloring
    from matplotlib.lines import Line2D
    custom_lines = [
        Line2D([0], [0], color='gray', alpha=0.3, lw=4),
        Line2D([0], [0], color='#2ca02c', marker='o', lw=0),
        Line2D([0], [0], color='#d62728', marker='X', lw=0)
    ]
    ax.legend(custom_lines, ['Allowed Limit', 'Pass (Dist ≤ Sens)', 'Violation (Dist > Sens)'])

    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300)
        print(f"Plot saved to {save_path}")
        
    if show:
        plt.show()
        
    return save_path