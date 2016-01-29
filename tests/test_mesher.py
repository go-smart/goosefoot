#!/usr/bin/python3

# This file is part of the Go-Smart Simulation Architecture (GSSA).
# Go-Smart is an EU-FP7 project, funded by the European Commission.
#
# Copyright (C) 2013-  NUMA Engineering Ltd. (see AUTHORS file)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# Go-Smart is an EU-FP7 project, funded by the European Commission.
#
# Copyright (C) 2013-  NUMA Engineering Ltd. (see AUTHORS file)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import tarfile
import time
import os
import pickle
from subprocess import check_output
from gssf import gssf


class ArgParseMock:
    def __init__(self, elmer_binary=None, outfilename=None, addpid=False, silent=True,
                 debug=False, nprocs=None, baw=True, only=None, leavetree=False, configfilenames=[]):
        self.elmer_binary = elmer_binary
        self.outfilename = outfilename
        self.addpid = addpid
        self.silent = silent
        self.debug = debug
        self.nprocs = nprocs
        self.baw = baw
        self.only = only
        self.leavetree = leavetree
        self.configfilenames = configfilenames


_script_dir = os.path.dirname(os.path.realpath(__file__))


def _check_mesh(launcher, runname, p, duration, expected_msh_size, expected_cells, expected_vertices, expected_time):
    time_tolerance = 0.2
    general_tolerance = 0.2

    msh_output = os.path.join(p, "mesher/%s.msh" % runname)

    assert(os.path.exists(msh_output))

    vtu_output = os.path.join(p, "mesher/%s.vtu" % runname)

    assert(os.path.exists(vtu_output))

    statinfo = os.stat(msh_output)

    # This is a pretty weak test, but it's a start
    # we expect at most a 50% variation in file size about
    # 200MB or something has probably gone wrong
    size_ratio = statinfo.st_size / expected_msh_size
    assert(size_ratio < 1. + general_tolerance and size_ratio > 1 - general_tolerance)

    vtk_analysis = pickle.loads(check_output(["python2", os.path.join(_script_dir, "vtk-analysis.py"), "-i", vtu_output]))
    number_of_vertices = vtk_analysis["vertices"]
    number_of_cells = vtk_analysis["cells"]

    if not isinstance(vtk_analysis, dict):
        raise RuntimeError("Did not run VTK analysis correctly")

    # More practical!
    assert(number_of_vertices > (1. - general_tolerance) * expected_vertices and
           number_of_vertices < (1. + general_tolerance) * expected_vertices)

    # More practical!
    assert(number_of_cells > (1. - general_tolerance) * expected_cells and
           number_of_cells < (1. + general_tolerance) * expected_cells)

    # Again, this doesn't tell us much, but it's a useful
    # sanity check. However fast the machine is, a serial
    # mesh should never finish in 30s - if it does, it hasn't
    # worked properly - it's just fooling us so far!
    if expected_time is not None:
        assert(duration > (1. - time_tolerance) * expected_time and
               duration < (1. + time_tolerance) * expected_time)


def test_mesher_cube(tmpdir):
    # This should take about 3s on an i7
    # producing an MSH ~170KB

    p = str(tmpdir.mkdir("mesher_cube"))

    t = tarfile.open(os.path.join(_script_dir, "data/mesher_cube.tar.gz"))
    t.extractall(p)

    args = ArgParseMock(configfilenames=["mesher_cube.xml"])

    cwd = os.getcwd()
    os.chdir(p)

    launcher = gssf.GSSF(args=args)

    start = time.time()
    launcher.launch(default_procs=1)
    duration = time.time() - start

    _check_mesh(launcher, "mesher_cube", p, duration,
                expected_msh_size=1.7e5, expected_cells=4.3e3,
                expected_vertices=9.4e2, expected_time=None)

    os.chdir(cwd)


def test_mesher_cube_dense(tmpdir):
    # This should take about 400s on an i7
    # producing an MSH ~200MB

    p = str(tmpdir.mkdir("mesher_cube_dense"))

    t = tarfile.open(os.path.join(_script_dir, "data/mesher_cube_dense.tar.gz"))
    t.extractall(p)

    args = ArgParseMock(configfilenames=["mesher_cube_dense.xml"])

    cwd = os.getcwd()
    os.chdir(p)

    launcher = gssf.GSSF(args=args)

    start = time.time()
    launcher.launch(default_procs=1)
    duration = time.time() - start

    _check_mesh(launcher, "mesher_cube_dense", p, duration,
                expected_msh_size=2e8, expected_cells=4.2e6,
                expected_vertices=7.2e5, expected_time=400)

    os.chdir(cwd)
