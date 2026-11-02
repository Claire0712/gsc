import importlib.util
from pathlib import Path
import numpy as np
import tempfile


def load():
    path = Path(__file__).resolve().parents[1] / 'scripts/build_precip_population_weights.py'
    assert path.is_file(), 'Native precipitation weight rebuild implementation missing'
    spec = importlib.util.spec_from_file_location('precip_native_weights', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native_grid_order_and_nearest_nodes():
    m = load()
    m.validate_era5_grid(np.arange(90., -90.01, -.1), np.arange(0., 360., .1))
    try:
        m.validate_era5_grid(np.arange(90., -90.01, -.25), np.arange(-180., 180., .25))
    except ValueError:
        pass
    else:
        raise AssertionError('Wrong native grid was accepted')
    rows, cols = m.nearest_era5_indices(np.array([90., 0., -90., 43.71]),
                                      np.array([0., -180., 359.99, 7.39]))
    assert rows.tolist() == [0, 900, 1800, 463]
    assert cols.tolist() == [0, 1800, 0, 74]


def test_native_population_mass_and_country_specific_cells(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import box
    m = load()
    source = tmp_path / 'population.tif'
    with rasterio.open(source, 'w', driver='GTiff', height=1, width=2, count=1,
                       dtype='float64', crs='EPSG:4326', transform=from_origin(0, .02, .02, .02)) as out:
        out.write(np.array([[2., 3.]]), 1)
    countries = [dict(country_id='A', geometry=box(0, 0, .02, .02)),
                 dict(country_id='B', geometry=box(.02, 0, .04, .02))]
    weights, totals, audit, _ = m.accumulate_population(source, countries, 1, 2, 'error')
    assert weights.shape == (2, 1801 * 3600)
    assert totals.tolist() == [2., 3.]
    assert audit['assigned_population_sum'] == 5.
    assert weights[0, 900 * 3600] == weights[1, 900 * 3600] == 1.


if __name__ == '__main__':
    test_native_grid_order_and_nearest_nodes()
    with tempfile.TemporaryDirectory() as directory:
        test_native_population_mass_and_country_specific_cells(Path(directory))
    print('Verified native grid and country-specific population mass tests')
