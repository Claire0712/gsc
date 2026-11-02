"""Supplementary data layer: every LOYO day-zero signed estimate and interval."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import hashlib
import json
from pathlib import Path
from matplotlib import font_manager

plt.rcParams.update({'font.sans-serif':['Arial'], 'axes.unicode_minus':False,
    'font.size':10, 'pdf.fonttype':42, 'mathtext.fontset':'custom',
    'mathtext.rm':'Arial', 'mathtext.it':'Arial:italic', 'mathtext.bf':'Arial:bold',
    'mathtext.default':'regular', 'svg.fonttype':'none'})
font_manager.findfont('Arial', fallback_to_default=False)
root = Path(__file__).resolve().parents[1]
source = root / 'deliverables/2026-10-28_LOYO_CURVES.json'
data = json.loads(source.read_text())
rows = [r for r in data['coefficients'] if r['term']=='heat_day_0' and r['outcome']=='signed']
assert len(rows)==12
output = root / 'deliverables/2026-10-28_figures_loyo'
assert not output.exists()
output.mkdir()
fig, axes = plt.subplots(3, 1, figsize=(7, 7.5), dpi=300)
for panel, (ax, signal, label, color) in enumerate(zip(axes,
        ('ping-slash24','bgp','merit-nt'), ('Active Probing','BGP','Network Telescope'),
        ('#3C5488','#00A087','#E64B35'))):
    selected = sorted((r for r in rows if r['signal']==signal), key=lambda r:r['omitted_reference_year'])
    beta = np.array([r['beta'] for r in selected])
    bounds = np.array([r['country_wild_basic95'] for r in selected])
    assert np.isfinite(bounds).all() and np.all(bounds[:,0]<=beta) and np.all(beta<=bounds[:,1])
    y = np.arange(4)
    ax.errorbar(beta, y, xerr=np.array([beta-bounds[:,0],bounds[:,1]-beta]),
        fmt='o', color=color, ecolor='#333333', elinewidth=1.5, capsize=3, capthick=1)
    ax.axvline(0, color='#666666', linestyle='--', linewidth=1)
    ax.set_yticks(y, [f"Omit {r['omitted_reference_year']}   ({r['groups']}/{r['countries']})" for r in selected])
    ax.invert_yaxis()
    ax.set_ylim(3.6,-.6)
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(1.0, decimals=2))
    ax.xaxis.set_major_locator(ticker.MaxNLocator(5))
    ax.spines[['top','right']].set_visible(False)
    ax.tick_params(direction='out')
    ax.text(0, 1.08, chr(97+panel), transform=ax.transAxes, fontweight='bold', fontsize=12)
    ax.text(.045, 1.08, label, transform=ax.transAxes, fontsize=11)
axes[-1].set_xlabel('Signed deviation on event day zero (normalized signal, %)', fontsize=12)
fig.tight_layout()
fig.subplots_adjust(hspace=.55)
for ext in ('pdf','svg','png'):
    fig.savefig(output/f'loyo_dayzero.{ext}', dpi=300, bbox_inches='tight')
plt.close(fig)
(output/'source_manifest.json').write_text(json.dumps(dict(
    source=str(source.relative_to(root)), sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    rows=rows, independent_panel_x_limits=True, figure_role='Supplementary reference sensitivity',
    outputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('loyo_dayzero.*')}),indent=2)+'\n')
