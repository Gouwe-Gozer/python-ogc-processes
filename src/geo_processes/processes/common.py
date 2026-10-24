"""Shared boundary checks and typed error mapping, without a processor framework."""

from collections.abc import Mapping
from contextlib import contextmanager

import rasterio
from pygeoapi.process.base import ProcessorExecuteError

from geo_processes import engine
from geo_processes.delivery import ResultCapacityError
from geo_processes.inputs import RasterInputBusyError, RasterInputError, RasterInputTooLargeError, resolve_json
from geo_processes.manager import InputBusyError, InputTooLargeError, InvalidExecutionRequestError
from geo_processes.storage import ResultStoreBusyError, ResultStoreError, ResultStoreFullError


@contextmanager
def processing_errors():
    try:
        yield
    except RasterInputTooLargeError as error:
        raise InputTooLargeError(user_msg=str(error)) from error
    except (RasterInputError, engine.RasterValidationError) as error:
        raise InvalidExecutionRequestError(str(error)) from error
    except RasterInputBusyError as error:
        raise InputBusyError(user_msg=str(error)) from error
    except (ResultStoreBusyError, ResultStoreFullError) as error:
        raise ResultCapacityError(user_msg=str(error)) from error
    except (ResultStoreError, rasterio.errors.RasterioError, OSError) as error:
        raise ProcessorExecuteError(user_msg="raster operation could not be completed") from error


def validate_inputs(data, *, allowed, required):
    if not isinstance(data, Mapping) or set(data) - allowed or not required <= data.keys():
        raise InvalidExecutionRequestError(
            f"inputs require {', '.join(sorted(required))}; supported: {', '.join(sorted(allowed))}"
        )


def integer_parameter(value, name, *, choices=None):
    value = resolve_json(value, name=name)
    if type(value) is not int or value < 1 or (choices is not None and value not in choices):
        raise RasterInputError(f"{name} must be a positive integer" + (f" in {choices}" if choices else ""))
    return value


def validate_band(path, band):
    with rasterio.Env(**engine.GDAL_OPTIONS), rasterio.open(path, driver="GTiff", GEOREF_SOURCES="INTERNAL") as raster:
        if band > raster.count:
            raise RasterInputError("band exceeds the source band count")
