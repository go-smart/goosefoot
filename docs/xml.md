# GSSF XML Configuration Format (GSSF-XML)

GSSF-XML is the workflow-specific configuration for a simulation. Along with
any STL input files, it is sufficient to run a simulation.

**Note that this
is distinct from the (workflow-independent) GSSA-XML format**. A processor, compiling
GSSA-XML to GSSF-XML is included in GSSA. The workflow-specific nature of
GSSF-XML gives it a distinctive character. A few sections are similar to the
GSSA-XML definition, in that they define over-arching problem characteristics
(such as geometry), but in GSSF-XML, each component of the workflow also has a
separate section with its own configuration.

## Format

This describes the general format of a GSSF-XML file.

    <gosmart [ debug="DEBUG:bool" ] [ version="GSSF_XML_VERSION:0.1.0" ] [ name="RUNNAME" ]>
          <geometry>
            <centre x="CX" y="CY" z="CZ" />
            <needleaxis x="NX" y="NY" z="NZ" />
            <simulationscaling ratio="SCALING" />
          </geometry>
          <regions>
            <surface|zone|both name="REGIONNAME" input="INPUTLOCATION" groups="GROUP1; GROUP2;..." />
            ...
          </regions>
          <constants>
            <constant name="PARAMNAME" value="PARAMVALUE" type="PARAMTYPE" />
            ...
          </constants>
        [ <needles>
            <needle name="NEEDLEID">
              [ <parameters>
                  <parameter name="PARAMNAME" value="PARAMVALUE" type="PARAMTYPE" />
                  ...
                </parameters> ]
            </needle>
            ...
          </needles> ]
        [ <needlelibrary>
            <!-- see 'Needle Library Component' -->
          </needlelibrary> ]
        [ <mesher>
            <!-- see 'Meshing Components' -->
          </mesher> ]
        [ <optimizer>
            <!-- see 'Optimizer Component' -->
          </optimizer> ]
        [ <elmergrid>
            <!-- see 'ElmerGrid Component' -->
          </elmergrid> ]
        [ <elmer>
            <!-- see 'ElmerSolver Component' -->
          </elmer> ]
        [ <lesion>
            <!-- see 'Lesion Component' -->
          </lesion> ]
        [ <validation>
            <!-- see 'Validation Component' -->
          </validation> ]
    </gosmart>

The XML version is given by `GSSF_XML_VERSION`. The latest version, described
here, is `0.1.0`. Note European spelling of `centre`.

## XML Schema

The documentation here should be adequate
to perform basic creation and manipulation of GSSF-XML.
However, in keeping with the increasing importance of
Docker-workflow and the presence of an automatic GSSA-XML &rarr; GSSF-XML
generator, this is secondary to the GSSA-XML formalization.
