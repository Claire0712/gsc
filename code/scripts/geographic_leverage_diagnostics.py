"""Matrix-only information diagnostics; never select or refit outcomes."""
import numpy as np
def diagnostics(x,z,countries,region_countries):
 countries=np.asarray(countries);other=np.column_stack([z,x[:,:-1]]);w=x[:,-1]-other@np.linalg.lstsq(other,x[:,-1],rcond=None)[0];tol=1e-9*max(1.,float(np.linalg.norm(w)));info={str(c):float(np.linalg.norm(w[countries==c])) for c in set(countries)};design=np.column_stack([z,x]);u,_,_=np.linalg.svd(design,full_matrices=False);rank=np.linalg.matrix_rank(design);hat=np.sum(u[:,:rank]**2,axis=1)
 return dict(rows=len(countries),countries=len(set(countries)),singleton_countries=int(sum(np.count_nonzero(countries==c)==1 for c in set(countries))),interaction_residual_information_countries=sum(t>tol for t in info.values()),interaction_residual_information_region_countries=sum(t>tol for c,t in info.items() if c in region_countries),interaction_residual_information_other_countries=sum(t>tol for c,t in info.items() if c not in region_countries),information_norm_threshold=tol,max_hat_diagonal=float(hat.max()),hat_diagonal_near_one=int(np.count_nonzero(hat>=1-1e-10)),scope='Descriptive information diagnostics, not a post-hoc exclusion or new fit.')

def comparison_qualification(d,min_countries=5):
 ok=all(d[k]>=min_countries for k in ('interaction_residual_information_region_countries','interaction_residual_information_other_countries'))
 return dict(qualified=ok,minimum_informative_countries_per_arm=min_countries,reason='' if ok else f'Below {min_countries} residual-information countries in at least one arm',scope='Post-hoc interpretation guard, independent of outcomes/p-values; retain every original numerical estimate and adjustment.')
