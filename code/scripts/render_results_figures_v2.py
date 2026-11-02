"""Render verified result JSON to editable scientific figures; no new estimates."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import json,hashlib,argparse
from pathlib import Path
from matplotlib import font_manager

plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial'],'axes.unicode_minus':False,'font.size':10,'pdf.fonttype':42,'svg.fonttype':'none','mathtext.fontset':'custom','mathtext.rm':'Arial','mathtext.it':'Arial:italic','mathtext.bf':'Arial:bold','mathtext.default':'regular'})

def run(output):
    out=Path(output)
    if out.exists():raise FileExistsError(out)
    font=font_manager.findfont('Arial',fallback_to_default=False);out.mkdir(parents=True)
    inputs={};captions={}
    def read(path,product):
        p=Path(path);m=json.loads((p/'manifest.json').read_text());raw=(p/product).read_bytes();h=hashlib.sha256(raw).hexdigest()
        if h!=m['outputs'][product]['sha256']:raise ValueError('Product hash mismatch')
        inputs[str((p/product).resolve())]=h;inputs[str((p/'manifest.json').resolve())]=hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest();return json.loads(raw)
    def style(ax,letter):
        ax.spines[['top','right']].set_visible(False);ax.tick_params(direction='out');ax.grid(axis='y',ls='--',alpha=.25);ax.set_axisbelow(True)
        if letter:ax.text(-.13,1.04,letter,transform=ax.transAxes,weight='bold',fontsize=12)
    def save(fig,name):
        fig.tight_layout()
        for ext in ('png','pdf','svg'):fig.savefig(out/(name+'.'+ext),dpi=300,bbox_inches='tight')
        plt.close(fig)
    signals=[('ap','AP','#3C5488'),('bgp','BGP','#00A087'),('merit-nt','Telescope','#E64B35')]
    fig,axes=plt.subplots(1,3,figsize=(10,3.2))
    for j,(short,label,color) in enumerate(signals):
        est=read(f'analysis/2026-10-13_hour_curve/v1/full_{short}_outputs','estimates.json');boot=read(f'analysis/2026-10-13_hour_wild/v1/full_{short}_outputs','bootstrap.json');days=np.array([int(v.replace('heat_day_','')) for v in est['terms'] if v.startswith('heat_day_')]);y=np.array(est['results']['signed']['beta'])[:len(days)];ci=np.array(boot['results']['signed']['basic_interval95'])[:len(days)]
        ax=axes[j];ax.axhline(0,color='#555555',ls='--',lw=1);ax.axvline(0,color='#777777',ls=':',lw=1);ax.vlines(days,ci[:,0],ci[:,1],color=color,alpha=.65,lw=1.3);ax.plot(days,y,'o-',color=color,lw=1.5,ms=3);ax.plot(-1,0,'s',color='#555555',ms=4)
        ax.set_xticks([-7,-3,-1,0,3,7]);ax.set_xlabel('Day relative to heat onset');ax.yaxis.set_major_formatter(ticker.PercentFormatter(1,decimals=2 if short=='bgp' else 1));style(ax,chr(97+j));ax.text(.04,.96,f'{label}\n{est["groups"]} matched events\n{est["countries"]} countries',transform=ax.transAxes,va='top',fontsize=9)
        if j==0:ax.set_ylabel('Signed connectivity difference')
    save(fig,'event_curve_signed')
    captions['event_curve_signed']='Signed connectivity event curves from the verified 10-minute main specification, relative to day -1 (fixed square). Bars are marginal 95% country WCU basic intervals, unrestricted and nonstudentized; not simultaneous bands. Each panel has its own y scale. Weights normalize reused control dates; event, matched-group-by-relative-day, country-hour-weekday and year-month effects and daily dewpoint retained. Country counts denote clusters, not independent 10-minute observations. All three day0 intervals include zero. Observational retrospective associations; no precipitation adjustment.'
    summary=read('analysis/2026-10-13_event_panel/v1/full_outputs','summary.json')
    keys=['no_significant_deficit','stable_recovered_before_end','awaiting_confirmation','damaged_at_end','delayed_onset','insufficient_observation'];names=['Maintained throughout','Stable recovery before end','Awaiting confirmation','Damaged at end','Delayed onset','Insufficient observation'];colors=['#00A087','#4DBBD5','#F39B7F','#E64B35','#3C5488','#B8B8B8']
    fig,ax=plt.subplots(figsize=(9,3.4));left=np.zeros(3)
    for key,name,color in zip(keys,names,colors):
        vals=np.array([summary['signals'][s]['all_forward']['states'].get(key,0)/910 for s in ['ping-slash24','bgp','merit-nt']]);ax.barh(np.arange(3),vals,left=left,color=color,label=name,height=.6,edgecolor='white',lw=.5);left+=vals
    np.testing.assert_allclose(left,1);ax.set_yticks(range(3),['AP','BGP','Telescope']);ax.invert_yaxis();ax.set_xlim(0,1);ax.xaxis.set_major_formatter(ticker.PercentFormatter(1));ax.set_xlabel('Share of forward heat events');style(ax,None);ax.grid(False);ax.legend(frameon=False,bbox_to_anchor=(1.01,1),loc='upper left',fontsize=9)
    save(fig,'event_state_distribution')
    captions['event_state_distribution']='Full-window technical states across 910 forward-routed Tmax events per signal (151 countries). The 294 held events are outside this denominator. Insufficient observation includes incomplete core or 72h followup/reference, and is explicitly retained rather than classified as healthy. State labels use95% maintenance and24-slot stable confirmation. This technical census precedes additional model-specific confound qualification and does not estimate causal heat-attributable outages or comparable global signal quality.'
    cox=read('analysis/2026-10-15_recovery_cox/v1/full_outputs','results.json');order=[('ping-slash24','primary'),('ping-slash24','complete72'),('merit-nt','primary'),('merit-nt','complete72')];labels=['AP: primary (14 recoveries)','AP: complete 72 h (13)','Telescope: primary (70)','Telescope: complete72h (62)'];fig,axes=plt.subplots(1,2,figsize=(9,3.8),sharey=True)
    for j,(model,term,xlabel) in enumerate([('M1','hd_c_days','Recovery hazard ratio per °C-day of HD'),('M2','ntrd_c_days','Recovery hazard ratio per °C-day of NTRD')]):
        ax=axes[j]
        for i,(sig,sample) in enumerate(order):
            r=next(r for r in cox if r['signal']==sig and r['sample']==sample and r['model']==model);k=r['terms'].index(term);y=r['hazard_ratio'][k];lo,hi=r['hazard_ratio95'][k];color='#3C5488' if sig=='ping-slash24' else '#E64B35';ax.errorbar(y,i,xerr=[[y-lo],[hi-y]],fmt='o' if sample=='primary' else 's',color=color,capsize=3,lw=1.5,ms=5)
        ax.axvline(1,color='#555555',ls='--',lw=1);ax.set_xscale('log');ax.xaxis.set_minor_formatter(ticker.NullFormatter());ax.set_xlim(.5,1.8);ax.set_xticks([.5,.75,1,1.5],['0.5','0.75','1','1.5']);ax.set_xlabel(xlabel);style(ax,chr(97+j));ax.grid(False)
    axes[0].set_yticks(range(4),labels);axes[0].invert_yaxis();save(fig,'conditional_recovery')
    captions['conditional_recovery']='Country-sandwich Cox hazard ratios and marginal normal95% intervals for conditional stable recovery among events damaged at end. Panel a:M1 HD adjusted for event span and dewpoint; panel b:M2 NTRD additionally adjusted for HD on identical M1/M2 samples. HR>1 means faster confirmation among damaged events. Primary AP27 and Telescope154 positive-followup records; complete clean72h AP23 and Telescope130 records. Complete72h sensitivity conditions on future observation. BGP has no qualified recovery endpoints and is not estimable. AP sparse estimates exploratory. No country fixed effects/calendar strata or multiplicity correction; neither conditional recovery nor these intervals establishes overall resilience or causal heat effects.'
    (out/'captions.json').write_text(json.dumps(captions,indent=2)+'\n')
    products={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
    (out/'manifest.json').write_text(json.dumps(dict(inputs=inputs,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),font=font,dpi=300,products=products),indent=2)+'\n')
    print(json.dumps(dict(output=str(out),figures=3,formats=['pdf','svg','png'],font=font)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args().output)
