# ElmerGrid GSSF Component

[ElmerGrid](ftp://ftp.funet.fi/index/elmer/doc/ElmerGridManual.pdf) is a tool in
the Elmer suite for converting meshes from non-Elmer formats to formats suitable
for the Elmer solver. It is capable of performing some other manipulations also,
and is generally used for scaling the meshes to metres prior to simulation.

The current implementation always adds a ``-removeunused`` flag. If the
simulation will use ``NP`` multiple processes, ``-metis NP`` is appended, and
``-scale X`` if some global scaling is required. Note that the scaling for the
simulation, from the original input mesh length-scale, normally takes place in
this component.

## Configuration

The ElmerGrid component is configured through an ``<elmergrid>`` node in the
GSSF-XML, as a first-level child.

    <elmergrid [ scale="X Y Z" ] [ skip="SKIP_ELMERGRID:false" ]>
    </elmergrid>

If ``simulationscaling`` constant is set globally and the ``scale`` attribute is
not provided, it will be used to set ElmerGrid scaling.

## Notes

* As the total simulation scaling is based on the scaling from the [Needle
Library](needle-library.md) and ElmerGrid components, they should appear in that
order in the XML.
