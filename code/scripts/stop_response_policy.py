"""Main finite STOP evidence is distinct from unknown-end scenario extensions."""
def require_main_clear(evidence):
    main=evidence.get('main')
    if not isinstance(main,dict) or set(main)!={'heat','control'}:raise ValueError('Missing main STOP evidence')
    if any(main.values()):raise ValueError('Selected main STOP overlap requires disposition')
    return {k:bool(any(v.values())) for k,v in evidence.items() if k!='main'}
