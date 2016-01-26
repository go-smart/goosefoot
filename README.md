Goosefoot (aka. GSSF)
=====================

A Tool-Specific Simulation Framework for Go-Smart
-------------------------------------------------

**Primary authors** : [NUMA Engineering Services Ltd](http://www.numa.ie) (NUMA), Dundalk, Ireland

**Project website** : http://www.gosmart-project.eu/

This project is co-funded by: European Commission under grant agreement no. 600641.

This tool, Goosefoot (GSSF), provides the necessary scripts and libraries to run a simulation workflow beginning from STL and VTP surfaces, configuring a [CGAL](https://cgal.org)-based tool for volumetric meshing, running [Elmer](https://elmerfem.org) for finite element simulation, and ending with a [VTK](https://vtk.org)-extracted isosurface.

Dependencies
------------

* Python 2.7
* Python 3
* [Elmer (with NUMA modifications)](https://github.com/go-smart/gssf-elmer)
* GMSH
* VTK 5.8
* libjsoncpp-dev
* (Python 3) munkres pyyaml
* (Python 2) PythonOCC

Documentation
-------------

Documentation for this component is available at https://go-smart.github.io/gssf

Installation
------------

CMake installation is recommended from an out-of-source build directory.

Usage
-----

The simulation workflow may be launched by the command

```sh
  go-smart-launcher settings.xml
```

where `settings.xml` is a GSSF-XML file. Adding --help will show documentation of command line arguments.
