"""Signal-specific selection with the original complete matched-sample gate."""
def select_rows(rows,signal):
    if signal not in ('ping-slash24','bgp','merit-nt'):raise ValueError('Unknown signal')
    selected=[r for r in rows if r['matched_integral'] and r['signal']==signal]
    if not selected or any(not r['metrics']['full_window_complete'] or not r['full_observed_unconfounded'] for r in selected):
        raise ValueError('Invalid matched sample')
    return selected
