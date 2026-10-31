ARG BASE_IMAGE=python-ogc-processes:0.1.0
FROM ${BASE_IMAGE}

# The base image puts /pygeoapi on PYTHONPATH for both the API and worker.
COPY examples/custom-process/custom_processes /pygeoapi/custom_processes
RUN /venv/bin/python3 -c 'from custom_processes.processor import TextStatisticsProcessor'
