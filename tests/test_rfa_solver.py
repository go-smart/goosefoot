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
from lxml import etree as ET
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


def _check_statistics(launcher, runname, p, duration, expected_threshold_cells, expected_stats, expected_time):
    time_tolerance = 0.2
    general_tolerance = 0.2

    analysis_output = os.path.join(p, "lesion", "%s-analysis.xml" % runname)

    assert(os.path.exists(analysis_output))

    statistics = ET.parse(analysis_output).getroot()

    assert(statistics is not None)

    for field, field_stats in expected_stats.items():
        field_node = statistics.find(field)

        # This ensures the test output will include the field name
        assert(field != "" and field_node is not None)

        for statistic, expected_value in field_stats.items():
            statistic_node = field_node.find(statistic)

            assert(statistic != "" and statistic_node is not None)

            try:
                value = float(statistic_node.text)
            except ValueError:
                value = None

            assert(value is not None)

            assert(abs(value - expected_value) < general_tolerance * abs(expected_value))

    threshold_cells = int(statistics.find("thresholdCells").text)
    assert(threshold_cells > (1. - general_tolerance) * expected_threshold_cells and
           threshold_cells < (1. + general_tolerance) * expected_threshold_cells)

    # This doesn't tell us much, but it's a useful
    # sanity check. However fast the machine is, a serial
    # mesh should never finish in 30s - if it does, it hasn't
    # worked properly - it's just fooling us so far!
    if expected_time is not None:
        assert(duration > (1. - time_tolerance) * expected_time and
               duration < (1. + time_tolerance) * expected_time)


def test_rfa_solver_cube(tmpdir):
    # This should take about 770s on an i7

    p = str(tmpdir.mkdir("rfa_solver_cube"))

    t = tarfile.open(os.path.join(_script_dir, "data/rfa_solver_cube.tar.gz"))
    t.extractall(p)

    args = ArgParseMock(configfilenames=["rfa_solver_cube.xml"])

    cwd = os.getcwd()
    os.chdir(p)

    launcher = gssf.GSSF(args=args)

    start = time.time()
    launcher.launch(default_procs=1)
    duration = time.time() - start

    stats = {
        "dead": {"maximum": 1.3, "mean": 0.36, "minimum": -0.58, "kurtosis": -1.6, "standardDeviation": 0.48},
        "temperature": {"maximum": 381.5, "mean": 335.4, "minimum": 309.6, "kurtosis": -1.54, "standardDeviation": 27.0},
    }
    threshold_cells = 7.23e4

    _check_statistics(launcher, "rfa_solver_cube", p, duration,
                      threshold_cells, stats, expected_time=685)

    os.chdir(cwd)


def test_rfa_solver_cube_dense(tmpdir):
    # This should take about 400s on an i7
    # producing an MSH ~200MB

    p = str(tmpdir.mkdir("rfa_solver_cube_dense"))

    t = tarfile.open(os.path.join(_script_dir, "data/rfa_solver_cube_dense.tar.gz"))
    t.extractall(p)

    args = ArgParseMock(configfilenames=["rfa_solver_cube_dense.xml"])

    cwd = os.getcwd()
    os.chdir(p)

    launcher = gssf.GSSF(args=args)

    start = time.time()
    launcher.launch(default_procs=1)
    duration = time.time() - start

    stats = {
        "dead": {"maximum": 1.20, "mean": 0.41, "minimum": -0.56, "kurtosis": -1.82, "standardDeviation": 0.477},
        "temperature": {"maximum": 374, "mean": 339, "minimum": 310, "kurtosis": -1.71, "standardDeviation": 27.0},
    }
    threshold_cells = 3.7e6

    _check_statistics(launcher, "rfa_solver_cube", p, duration,
                      threshold_cells, stats, expected_time=None)

    os.chdir(cwd)
