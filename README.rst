|Version| |Python| |Tests| |License|

RPyC-NG_ (pronounced like *are-pie-see next generation*), or *Remote Python Call Next Generation*, is a
**transparent** library for **symmetrical** `remote procedure calls`_,
clustering_, and distributed-computing_.  RPyC-NG makes use of object-proxying_,
a technique that employs python's dynamic nature, to overcome the physical
boundaries between processes and computers, so that remote objects can be
manipulated as if they were local. It is based on the RPyC_ works from
`Tomer Filiba`_ which does not seem to be maintained any longer.

Documentation can be found at https://rpyc-ng.readthedocs.io

.. figure:: https://github.com/rlehfeld/rpyc-ng/blob/main/docs/_static/screenshot.png
   :align: center

   A screenshot of a Windows client connecting to a Linux server.

   Note that text written to the server's ``stdout`` is actually printed on
   the server's console.


.. References:

.. _RPyC-NG:                https://github.com/rlehfeld/rpyc-ng
.. _RPyC:                   https://github.com/tomerfiliba-org/rpyc
.. _remote procedure calls: http://en.wikipedia.org/wiki/Remote_procedure_calls
.. _clustering:             http://en.wikipedia.org/wiki/Clustering
.. _distributed-computing:  http://en.wikipedia.org/wiki/Distributed_computing
.. _object-proxying:        http://en.wikipedia.org/wiki/Proxy_pattern
.. _Tomer Filiba:           https://github.com/tomerfiliba

.. Badges:

.. |Version| image::   https://img.shields.io/pypi/v/rpyc-ng.svg?style=flat
   :target:            https://pypi.org/project/rpyc-ng
   :alt:               Version

.. |Python| image::    https://img.shields.io/pypi/pyversions/rpyc-ng.svg?style=flat
   :target:            https://pypi.org/project/rpyc-ng#files
   :alt:               Python Versions

.. |Tests| image::     https://github.com/rlehfeld/rpyc-ng/actions/workflows/python-app.yml/badge.svg
   :target:            https://github.com/rlehfeld/rpyc-ng/actions/workflows/python-app.yml
   :alt:               Build Status

.. |License| image::   https://img.shields.io/pypi/l/rpyc-ng.svg?style=flat
   :target:            https://github.com/rlehfeld/rpyc-ng/blob/main/LICENSE
   :alt:               License: MIT
