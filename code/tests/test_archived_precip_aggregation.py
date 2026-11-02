from pathlib import Path
import sys
import importlib.util
import numpy as np
from scipy import sparse


def load():
    p=Path(__file__).resolve().parents[1]/'scripts/aggregate_archived_precip.py'
    assert p.exists(), 'Precipitation aggregation implementation missing'
    sys.path.insert(0,str(p.parents[1]))
    spec=importlib.util.spec_from_file_location('scripts.aggregate_archived_precip',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def test_finite_population_denominator_and_units():
    m=load()
    w=sparse.csr_matrix([[2.,3.,0.],[0.,0.,0.]])
    means,fractions=m.precip_statistics(w,np.array([.001,np.nan,0.]))
    assert means[0]==1. and fractions[0]==.4
    assert np.isnan(means[1]) and np.isnan(fractions[1])
    means,fractions=m.precip_statistics(w,np.array([0.,0.,np.nan]))
    assert means[0]==0. and fractions[0]==1.


def test_accumulation_day_is_previous_utc_date():
    m=load()
    assert m.accumulation_date(1640995200)=='2021-12-31'
    assert m.accumulation_date(1709251200)=='2024-02-29'
    try:m.accumulation_date(1640995201)
    except ValueError:pass
    else:raise AssertionError('Non-midnight accumulation label accepted')


def test_archived_unit_bytes_are_decoded_not_changed():
    m=load()
    m.validate_units(b'm');m.validate_units('m')
    try:m.validate_units(b'mm')
    except ValueError:pass
    else:raise AssertionError('Wrong precipitation units accepted')


if __name__=='__main__':
    test_finite_population_denominator_and_units()
    test_accumulation_day_is_previous_utc_date()
    test_archived_unit_bytes_are_decoded_not_changed()
    print('Verified finite support, zero, missing, unit and accumulation-date tests')
