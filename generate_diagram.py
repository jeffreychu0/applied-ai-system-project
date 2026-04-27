"""
generate_diagram.py
===================
Generates assets/system_architecture.png — a visual map of the PawPal+
system showing components, data flow, and the testing / human-evaluation layer.

Run from the project root:
    python generate_diagram.py
"""
import os

import matplotlib
matplotlib.use('Agg')  # headless rendering — no display needed
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# ─────────────────────────────────────────────────────────────────────────────
# Canvas
# ─────────────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(20, 12))
ax = fig.add_axes([0, 0, 1, 1])   # axes fills the entire figure — no margins
ax.set_xlim(0, 20)
ax.set_ylim(0, 12)
ax.axis('off')
ax.set_facecolor('#F0F4F8')
fig.patch.set_facecolor('#F0F4F8')

# ─────────────────────────────────────────────────────────────────────────────
# Colour palette
# ─────────────────────────────────────────────────────────────────────────────
C = dict(
    user   = '#1565C0',  # deep blue
    ui     = '#2E7D32',  # deep green
    agent  = '#E65100',  # deep orange
    openai = '#6A1B9A',  # purple
    domain = '#00695C',  # teal
    output = '#37474F',  # blue-grey
    test   = '#C62828',  # deep red
    human  = '#4E342E',  # brown
    arrow  = '#455A64',
    darrow = '#90A4AE',  # dashed arrows
)

# ─────────────────────────────────────────────────────────────────────────────
# Drawing helpers
# ─────────────────────────────────────────────────────────────────────────────

def container(x, y, w, h, label, fc, ec):
    r = FancyBboxPatch(
        (x, y), w, h,
        boxstyle='round,pad=0.15',
        facecolor=fc, edgecolor=ec,
        linewidth=2, linestyle='--',
        zorder=1, alpha=0.55,
    )
    ax.add_patch(r)
    ax.text(x + 0.22, y + h - 0.16, label,
            ha='left', va='top', fontsize=9,
            color='#263238', fontweight='bold', zorder=2)


def node(cx, cy, w, h, label, color, sub=None, fs=9):
    r = FancyBboxPatch(
        (cx - w / 2, cy - h / 2), w, h,
        boxstyle='round,pad=0.1',
        facecolor=color, edgecolor='white',
        linewidth=2.5, zorder=3,
    )
    ax.add_patch(r)
    if sub:
        ax.text(cx, cy + 0.18, label, ha='center', va='center',
                fontsize=fs, fontweight='bold', color='white', zorder=5)
        ax.text(cx, cy - 0.18, sub, ha='center', va='center',
                fontsize=fs - 1.5, color='white', alpha=0.9, zorder=5)
    else:
        ax.text(cx, cy, label, ha='center', va='center',
                fontsize=fs, fontweight='bold', color='white', zorder=5)


def arrow(x1, y1, x2, y2, color=C['arrow'], dashed=False,
          bidir=False, rad=0.0, lbl='', lbl_dx=0.15):
    ls = (0, (5, 4)) if dashed else 'solid'
    style = '<->' if bidir else '->'
    ax.annotate(
        '', xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle=style, color=color, lw=1.6,
            linestyle=ls,
            connectionstyle=f'arc3,rad={rad}',
            shrinkA=6, shrinkB=6,
        ),
        zorder=4,
    )
    if lbl:
        mx = (x1 + x2) / 2 + lbl_dx
        my = (y1 + y2) / 2
        ax.text(mx, my, lbl, fontsize=6.5, color=color, zorder=5)


# ─────────────────────────────────────────────────────────────────────────────
# Containers  (drawn first — lowest z-order)
# ─────────────────────────────────────────────────────────────────────────────
container(0.3,  7.5, 9.0, 2.0, 'Streamlit Frontend  (app.py)',    '#E8F5E9', '#81C784')
container(9.5,  7.5, 9.8, 2.0, 'AI Agent  (agent.py)  +  OpenAI', '#FFF3E0', '#FFB74D')
container(1.0,  5.2, 16.0,1.9, 'Domain Model  (pawpal_system.py)', '#E0F7FA', '#4DD0E1')
container(2.5,  2.8, 13.5,1.9, 'Output Layer',                     '#ECEFF1', '#90A4AE')
container(0.3,  0.2, 16.0,1.9, 'Testing & Human Evaluation',       '#FFEBEE', '#EF9A9A')

# ─────────────────────────────────────────────────────────────────────────────
# Nodes
# ─────────────────────────────────────────────────────────────────────────────
# Row 0 — User (input)
node(10.0, 11.3, 3.0, 0.65, 'USER  (Input)', C['user'])

# Row 1 — Streamlit UI
node(2.7,  8.55, 3.0, 0.95, 'Manual Tabs',   C['ui'],    'Tasks / Schedule / Filter / Conflicts')
node(6.8,  8.55, 2.6, 0.95, 'AI Chat Tab',   C['ui'],    'Chat Interface')

# Row 1 — AI Agent + OpenAI
node(10.5, 8.55, 2.8, 0.95, 'Agentic Loop',    C['agent'],  'run_agent_turn()')
node(14.0, 8.55, 2.8, 0.95, 'Tool Executor',   C['agent'],  'execute_tool()')
node(18.0, 8.55, 2.5, 0.95, 'OpenAI API',      C['openai'], 'gpt-4o-mini')

# Row 2 — Domain Model
node(3.5,  6.2, 3.2, 0.95, 'Session State',      C['domain'], 'Owner / Pets / Tasks')
node(8.8,  6.2, 2.8, 0.95, 'Scheduler',           C['domain'], 'build_schedule()')
node(14.5, 6.2, 3.2, 0.95, 'Conflict Detector',   C['domain'], 'detect_conflicts()')

# Row 3 — Outputs
node(6.0,  3.75, 4.2, 0.95, 'Schedule & Task View', C['output'], 'Conflict Report')
node(12.5, 3.75, 3.2, 0.95, 'AI Reply',             C['output'], 'Action Confirmation')

# Row 4 — Testing
node(2.0,  1.15, 2.8, 0.8, 'test_pawpal.py',    C['test'],  '47 Domain Tests',  fs=8.5)
node(5.5,  1.15, 2.8, 0.8, 'test_agent.py',      C['test'],  'Tool Tests',       fs=8.5)
node(9.0,  1.15, 2.8, 0.8, 'Integration Tests',  C['test'],  'Live API Calls',   fs=8.5)
node(13.0, 1.15, 3.0, 0.8, 'Human Evaluator',    C['human'], 'Manual Validation',fs=8.5)

# Row 5 — User (output)
node(10.0, 0.42, 3.0, 0.55, 'USER  (Output)', C['user'])

# ─────────────────────────────────────────────────────────────────────────────
# Arrows — main data flow  (solid)
# ─────────────────────────────────────────────────────────────────────────────
# User → UI
arrow(9.3, 11.0, 3.5, 9.03,  lbl='form input',    lbl_dx=0.15)
arrow(9.7, 11.0, 7.2, 9.03,  lbl='chat message',  lbl_dx=0.15)

# Manual Tabs → Session State
arrow(2.7, 8.08, 3.5, 6.68,  lbl='CRUD')

# AI Chat → Agentic Loop
arrow(8.1, 8.55, 9.1, 8.55)

# Agentic Loop → OpenAI  (above tool executor — positive rad arcs upward)
arrow(11.9, 8.8, 16.75, 8.8,  rad=-0.25, lbl='prompt + history', lbl_dx=0.1)

# OpenAI → Tool Executor  (function calls)
arrow(16.75, 8.3, 15.4, 8.3,  rad=0.25,  lbl='function calls',  lbl_dx=-1.1)

# Tool Executor → OpenAI  (tool results)
arrow(15.4, 8.8, 16.75, 8.8,  rad=0.25,  lbl='tool results',    lbl_dx=0.1)

# OpenAI → Agentic Loop  (final reply — below the row)
arrow(16.75, 8.3, 11.9, 8.3,  rad=0.25, lbl='final reply',      lbl_dx=0.1)

# Tool Executor ↔ Session State  (reads/writes, long diagonal)
arrow(14.0, 8.08, 4.0, 6.68,  bidir=True, rad=0.1, lbl='reads / writes', lbl_dx=0.15)

# Session State → Scheduler
arrow(5.1, 6.2, 7.4, 6.2,  lbl='tasks')

# Scheduler → Conflict Detector
arrow(10.2, 6.2, 12.9, 6.2)

# Domain → Output
arrow(3.5, 5.73, 5.2, 4.22,  lbl='task data')
arrow(8.8, 5.73, 6.8, 4.22)
arrow(14.5,5.73, 12.5,4.22,  lbl='conflicts')

# Agentic Loop → AI Reply  (curved, routes right of domain)
arrow(10.5, 8.08, 12.5, 4.22,  rad=-0.2, lbl='AI reply', lbl_dx=0.2)

# Output → User (output)
arrow(6.0,  3.28, 8.8,  0.7)
arrow(12.5, 3.28, 11.2, 0.7)

# ─────────────────────────────────────────────────────────────────────────────
# Arrows — testing & evaluation  (dashed, muted colour)
# ─────────────────────────────────────────────────────────────────────────────
D = C['darrow']
# Domain/Agent/API → test boxes
arrow(3.5,  5.73, 2.0,  1.55,  dashed=True, color=D)          # State → tdom
arrow(14.0, 8.08, 5.5,  1.55,  dashed=True, color=D, rad=0.1) # Tools → tagent
arrow(18.0, 8.08, 9.0,  1.55,  dashed=True, color=D, rad=0.2) # OpenAI → tinteg

# Test boxes → Human Evaluator
arrow(3.4,  1.15, 11.5, 1.15,  dashed=True, color=D)
arrow(6.9,  1.15, 11.5, 1.15,  dashed=True, color=D)
arrow(10.4, 1.15, 11.5, 1.15,  dashed=True, color=D)

# Human Evaluator → Agentic Loop  (feedback loop)
arrow(13.0, 1.55, 10.5, 8.08,  dashed=True, color=D, rad=-0.3, lbl='feedback', lbl_dx=0.2)

# ─────────────────────────────────────────────────────────────────────────────
# Title
# ─────────────────────────────────────────────────────────────────────────────
ax.text(10, 11.82, 'PawPal+  -  System Architecture',
        ha='center', va='center',
        fontsize=17, fontweight='bold', color='#1A237E')

# ─────────────────────────────────────────────────────────────────────────────
# Legend
# ─────────────────────────────────────────────────────────────────────────────
legend_handles = [
    mpatches.Patch(color=C['user'],   label='User'),
    mpatches.Patch(color=C['ui'],     label='Frontend (Streamlit)'),
    mpatches.Patch(color=C['agent'],  label='AI Agent'),
    mpatches.Patch(color=C['openai'], label='LLM  (OpenAI)'),
    mpatches.Patch(color=C['domain'], label='Domain Model'),
    mpatches.Patch(color=C['output'], label='Output'),
    mpatches.Patch(color=C['test'],   label='Testing'),
    mpatches.Patch(color=C['human'],  label='Human Evaluation'),
]
ax.legend(
    handles=legend_handles,
    loc='lower right',
    bbox_to_anchor=(19.8, 0.2),
    fontsize=8.5, framealpha=0.9, ncol=1,
    title='Layer', title_fontsize=9,
    edgecolor='#90A4AE',
)

# ─────────────────────────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────────────────────────
os.makedirs('assets', exist_ok=True)
plt.savefig(
    'assets/system_architecture.png',
    dpi=150,
    facecolor='#F0F4F8',
)
plt.close()
print('Saved: assets/system_architecture.png')
