# ElmerSolver GSSF Component

[ElmerSolver](www.nic.funet.fi/index/elmer/doc/ElmerSolverManual.pdf) is the
simulation tool within the Elmer suite. This GSSF component prepares
configuration for it based on the GSSF-XML input, runs it and monitors it for
percentage progress.

## Elmer SIF template

The Elmer SIF provides the configuration of the solver. It is generated from
a [Jinja2](http://jinja.pocoo.org/) template, which is supplied in the GSSF-XML.
Parameter dictionaries provide access to the global GSSF parameter list
from the template - see [Constants (Parameters)](../constants.md) for more detail.

In addition to the global parameter dictionary, `p`, and the dictionary of
needle parameter dictionaries `needles`, there is a counter dictionary, `c`. It may used
in a similar fashion to the parameter dictionaries, by member syntax. If a
member `c.BODY`, say, has not been used before, its first usage will return `1`.
The second will return `2` and so forth. Prefixing the member with an
underscore, `c._BODY` will return the current index without incrementing.

Note that, while the GSSA simulation server scrubs SIF files, GSSF itself does
not. As such, if running GSSF separately **you should only accept SIF templates from trusted sources**,
Specifically, several MATC functions provide access to the filesystem or printf,
so precautions should be taken.

[Algorithms](https://go-smart.github.io/gssa/algorithms/) in MATC will be written to a file with a unique
ID. A line sourcing it will be added at the end of the SIF, and the constant
representing the result, will be substituted with a call to it. For instance,
`Electric conductivity = {{ p.ELECTRIC_CONDUCTIVITY }}`, when with an algorithm
with result `ELECTRIC_CONDUCTIVITY` based on Argument `Temperature` is provided,
would become:

    Electric conductivity = Variable Temperature
        Real MATC "ELECTRIC_CONDUCTIVITY(tx(0))"

The following filters are available, in addition to basic Jinja2 sandbox
filters:

Filter name | Apply to | Purpose | Parameters
------------|----------|---------|-----------
`typed` | Parameter | render parameter with SIF type prefix | -
`totyped` | any Parameter-wrappable value | render value with SIF type prefix based on type *d* | *d* (desired type)
`discretize` | number | round to nearest *r* (returns int if *r* &gt;= 1) | *r* (granularity)

The following global functions are available, in addition to basic Jinja2
sandbox globals:

Function | Arguments | Description
---------|-----------|------------
`zip` | as usu. | Python built-in
`list` | as usu. | Python built-in
`map` | as usu. | Python built-in
`str` | as usu. | Python built-in
`needle_distance` | *needle1id*,<br/>*needle2id*,<br/>(opt) *d*,<br/>(opt) *ref* | returns the perpendicular distance between *needle1* and *needle2*, optionally starting from *d* metres (or simulation scale) along shaft from tip of needle *ref* (*needle1id* or *needle2id*)

**TIP**: Elmer tends to die without reporting an error if there is a problem with a MATC function,
sometimes with a segfault or an unpredictable number output. If you notice you
are getting simulations failing at the solver step, it is recommended that you
run `ElmerSolver_mpi` manually in the `elmer` folder to see
whether this is the case. If so, removing and progressively adding in MATC
functions should clarify which is causing the problem.

## Status updates

The solver module starts a socket listening on `percentage.sock` in the simulation
directory. An Elmer solver (`NumaProgress`) is available to connect to and update this based on
the solver `Percentage Progress` value. By adding this solver into your SIF file
and setting `Percentage Progress` within it, you can receive percentage updates in the main
Python process.

TODO: Add in user-configurable status text, after checking for security issues that may rise.

## Runtime compilation

Models can be tagged with certain library Fortran modules, which are then used
in the SIF file as user-defined functions (UDFs). For security reasons, only
predefined modules are available, such as `mwa_RelPerm` or `mwa_ElecCond`, which
provide temperature-dependent relative permittivity and electric conductivity
for microwave ablation. These modules can contain GSSF constants, which are
inserted before compilation. They must be cast to numeric types only to
prevent injection and it is recommended that any new modules are used only in
standalone mode with trusted template input.

In general, it is recommended to avoid this method
as it is harder to abstract and errors in adding modules can compromise security,
at least until GSSF is reorganised for use inside
the Docker workflow and sandboxing allows for user-supplied routines.

## Point source location factories

For the point source models, where a series of heating points defines the input
power distribution, a factory is used to simplify setting of models. The factory
can output locations at various probe extensions without these needing to be
pre-calculated on the client-side, or in the CDM. For this to work correctly, at
least in the current version, there must only be one needle present in a
simulation at a time. If needed, a workaround may be to add additional heating
points for a secondary needle to the first, provided all extension lengths and
times match.

Several probe location factories are contained in the GSSF codebase. These may
be extended by subclassing ``GoSmartElmerProbeLocationFactory`` and adding to
the dictionary, ``gssf.elmer_probelocation.probe_location_factories``.

A number of thermocouples may be defined, which can be used to label each of the
heating points. These are passed to the actual solver and,
normally, used to switch points on and off according to some thermocouple-based
algorithm. The remaining points are split between ``ends`` and ``middles``,
which are generally used to distribute power between two different levels by
the simulation module.

The default factories are outlined below.

### Manual Probe Location Factory

`GoSmartElmerProbeLocationFactoryManual` is selected by setting the point
sources ``system`` to ``manual``. This requires all points to be configured for
GSSF-XML and assumes a single extension.

The ``pointsources`` XML block should be formatted as follows:

    <pointsources system="manual">
      [(
        <ends|middles|thermocouples>
          <location x="X1" y="Y1" z="Z1" t="T1" />
          ...
        </ends|middles|thermocouples>
      |
        <ends|middles|thermocouples input="block">
            X1	Y1	Z1	T1 (tabbed)
          ...
        </ends|middles|thermocouples>
      )]*
    </pointsources>

where ``T``, an integer, is the index of the controlling thermocouple in the
list of point sources.

### Straight Tines Location Factory

`GoSmartElmerProbeLocationFactoryStraightTines` generates all point locations
based only on the shaft location and (scalar) extensions. It assumes the locus
from shaft tip to the end of each of the tines is linear. Note that this does
not, strictly, equate to the tine itself being linear, but states that there
should be a `middle` heating point at the mid-point of a line from the shaft tip to each
`end` point.

The ``pointsources`` XML block should be formatted as follows:

    <pointsources system="straight tines" [ offset="X Y Z" ]>
      <extensions>
        <extension phase="0" length="L1"/>
        <extension phase="1" length="L2"/>
        ...
      </extensions>
    </pointsources>

The `offset` parameter allows the user to change the point location relative to
the needle-shaft tip. The shaft location is taken from the geometry section.
`Ln` lengths should be provided in metres.
Note that the change of phase over time is usually controlled via a simulation module.

### Umbrella Tines Location Factory

`GoSmartElmerProbeLocationFactoryUmbrellaTines` provides an arched configuration
of heating points, where the `end` is perpendicular to the tip and the `middle`
is at an angle beyond the tip, such that opposing tines form an M shape.

Configuration is identical to the [Straight Tines Location
Factory](#straight-tines-location-factory), using `system="umbrella tines"`.

### Extrapolated Tine Factory

`GoSmartElmerProbeLocationFactoryExtrapolated` takes the tip locations for the
largest extension and scales accordingly for other extensions. Note that
clinicians generally do imaging showing full extension before starting the
protocol (at least, in radiofrequency ablation), so this location information is
available at the beginning of the procedure.

The `pointsources` XML block should be formatted as follows:

    <pointsources system="extrapolated" [ offset="X Y Z" ]>
      <extensions>
        <extension phase="0" length="L1"/>
        <extension phase="1" length="L2"/>
        ...
      </extensions>
      <points>
        <point i="1" x="X1" y="Y1" z="Z1"/>
        <point i="2" x="X2" y="Y2" z="Z2"/>
        ...
      </points>
    </pointsources>

## Configuration

The XML format for the `<elmer>` first-level configuration node is as follows:

    <elmer [ skip="SKIP_ELMER:false" ]>
        [ <restart time="RESTART_TIME" position="RESTART_INDEX" old="PREVIOUS_SIF_PREFIX" /> ]
        [ <pointsources system="TINE_FACTORY">
            <!-- AS DEFINED ABOVE -->
          </pointsources> ]
        (
          <variant [ modules="f90module1; f90module2;..." ] name="SIF_TEMPLATE_LIBRARY_NAME" />
        |
          <variant [ modules="f90module1; f90module2;..." ] >
            ! SIF TEMPLATE
            !
            ...
          </variant>
        )
        [ <settings>
            <setting|constant name="non-slug setting name" value="CONSTANT_VALUE" type="CONSTANT_TYPE" />
            ...
          </settings> ]
        [ <algorithms>
            <algorithm>
                <arguments>
                  <argument name="ARGUMENT_NAME" />
                </arguments>
                <content>
                  <!-- Algorithm content - usu. MATC -->
                </content>
            </algorithm>
            ...
          </algorithms> ]
    </elmer>

Note that `non-slug setting name` will translate to
`SETTING_NON_SLUG_SETTING_NAME` in the SIF parameter dictionary.
