"""Use unchanged weather estimator with an explicit exact-month LOYO lineage gate."""
import argparse
from . import run_variant_pre_weather as driver
from . import variant_weather_sources
from .loyo_weather_sources import resolve_sources

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for arg in ('comparison', 'heat', 'weather', 'output', 'batch', 'source-heat'):
        parser.add_argument('--' + arg, required=True)
    parser.add_argument('--country')
    args = parser.parse_args()
    # Process-local, explicit dependency substitution; frozen modules stay on disk unchanged.
    variant_weather_sources.resolve_sources = lambda heat, batch, original, sources: resolve_sources(heat, batch, original, sources, args.weather)
    driver.run(args)
