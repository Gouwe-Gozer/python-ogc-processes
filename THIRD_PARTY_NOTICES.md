# Third-party notices

Raster Processes API is maintained by Minnert Wijnands (Gouwe-Gozer) and is
MIT-licensed. The following notices identify reused application code and
dependencies, whose licences also apply to their respective software.

## Project origins: bkn-terrain-processes

This project derives reusable pygeoapi integration, tests and deployment
infrastructure from the MIT-licensed
[Gouwe-Gozer/bkn-terrain-processes](https://github.com/Gouwe-Gozer/bkn-terrain-processes)
project. Its original notice is retained in [LICENSE](LICENSE):

```text
Copyright (c) 2026 Breinstein Informatiemanagement B.V.
```

The original MIT permission and warranty terms remain unchanged. The additional
copyright for changes in this project names Minnert Wijnands (Gouwe-Gozer).
The origin acknowledgement does not imply involvement in this project's
maintenance.

## pygeoapi 0.24.0

- Project: [geopython/pygeoapi](https://github.com/geopython/pygeoapi)
- Licence: MIT

```text
The MIT License (MIT)

Copyright &copy; 2018-2026 pygeoapi development team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Rasterio 1.4.3

- Project: [rasterio](https://github.com/rasterio/rasterio)
- Licence: BSD-3-Clause
- Full bundled-library notices remain with the installed distribution.

```text
Copyright (c) 2013-2021, Mapbox
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of Mapbox nor the names of its contributors may
  be used to endorse or promote products derived from this software without
  specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

## NumPy 1.26.4

- Project: [numpy](https://github.com/numpy/numpy)
- Licence: BSD-3-Clause
- Full bundled-library notices remain with the installed distribution.

```text
Copyright (c) 2005-2023, NumPy Developers.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

    * Redistributions of source code must retain the above copyright
       notice, this list of conditions and the following disclaimer.

    * Redistributions in binary form must reproduce the above
       copyright notice, this list of conditions and the following
       disclaimer in the documentation and/or other materials provided
       with the distribution.

    * Neither the name of the NumPy Developers nor the names of any
       contributors may be used to endorse or promote products derived
       from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

## PostgreSQL job-management dependencies

- [psycopg2-binary 2.9.11](https://www.psycopg.org/): LGPL version 3 or later
  with the exceptions in its bundled `LICENSE`. Bundled-library notices remain
  with the installed distribution.
- [GeoAlchemy2 0.20.0](https://geoalchemy-2.readthedocs.io/): MIT. Required by the
  stock pygeoapi PostgreSQL manager's SQL-provider imports; job storage does not
  require a PostGIS extension.
- [SQLAlchemy](https://www.sqlalchemy.org/): MIT. Already supplied through
  pygeoapi and now explicitly declared for the application's transactional job
  integration; the resolved version is recorded in `uv.lock`.

The installed distributions retain their respective copyright/licence files.

## Opt-in contributor experience integrations

The disposable integration experiment declares existing locked packages directly:

- Shapely 2.1.2: BSD-3-Clause; its installed distribution retains `LICENSE.txt`
  and the bundled GEOS notice `LICENSE_GEOS`.
- PyProj 3.7.2: MIT; its installed distribution retains `LICENSE` and
  the bundled PROJ notice `LICENSE_proj`.
- Requests 2.34.2: Apache-2.0; its installed distribution retains `LICENSE`
  and `NOTICE`.

`src/geo_processes/operations/terrain.py` extracts only terrain analysis from
the user-supplied `bird-detections-main/ingestion/sync_terrain.py`. No copyright
or licence notice was present in that supplied script. The associated Alkmaar
boundary is copied unchanged. No new licence is asserted for these supplied
materials; their provenance and checksums are recorded in the experiment
[report](examples/contributor-experience/REPORT.md). They are not registered in
the default catalogue.

## Packaged sample data

The AHN4 sample GeoTIFF is published as AHN data under CC0 1.0, separately from
the software licences above. Source links and its checksum are recorded in
[sample data](docs/sample-data.md).
