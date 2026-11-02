"""Breslow risk-set likelihood with optional log-time slope interactions."""
import numpy as np
from scipy.special import logsumexp

def objective(beta,x,t,d,time_interaction=False):
    value=0.;grad=np.zeros(len(beta))
    for time in np.unique(t[d==1]):
        event=(t==time)&(d==1);risk=t>=time
        z=np.column_stack([x,x*np.log(time/24)]) if time_interaction else x
        eta=z[risk]@beta;logden=logsumexp(eta);prob=np.exp(eta-logden);n=event.sum()
        value+=n*logden-np.sum(z[event]@beta)
        grad+=n*(prob@z[risk])-z[event].sum(axis=0)
    return float(value),grad
