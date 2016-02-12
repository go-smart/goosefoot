# Constants in GSSF

In GSSF code, parameters are generally referred to as ``constants``, which is not
entirely accurate, but reflects the fact that the definition itself does
not usually change throughout the simulation. They are generally
floats/ints/etc. but may be MATC functions that are dropped into the SIF at the
start of the simulation.

Constants in GSSF mostly arise from the parameters set in the GSSF-XML, but
include other values such as the mesh scaling, which is not (in GSSF) in the
parameter section. They are also used to transfer certain values between
components, where one calculates and adds a constant to the global space and
another uses it.

## Parameters in the Elmer SIF template

The [SIF template](components/elmer.md#elmer-sif-template) is a
[Jinja2](http://jinja.pocoo.org/) template. As such, Python parameter
dictionaries are used to pass parameters into the template. These are named `p`
and `needles`, being the global and needle-specific parameters, respectively. The
needle parameter dictionary, `needles`, is a dictionary of parameter dictionaries,
indexed as integers based on the needle indexes from the GSSF-XML.

The parameter dictionaries are of class `ParameterDict`, which extends Python's
`dict` built-in. In particular, these can be used with the member syntax:
`p.CONSTANT_BODY_TEMPERATURE`, for example, will return the relevant `Parameter`
object for that parameter. This actually covers all global constants, not just
the GSSF parameters, so a few extra items are available. For instance,
`p.NEEDLE_AXIS_SCALE_X` will return the scaling in the *x* direction used by the
needle library.

The `Parameter` class, to which the returned parameters belong, is castable to
float, int and string. The Jinja filter `typed` will cause it to be output with
its SIF type as a prefix (useful, for example, when assigning to a property in
the SIF file). If not otherwise cast, it will appear as a string representation.
If the parameter type is an array, it will be converted to a space separated
list.

For instance, if the following line appears in the SIF template:

    ...
    Power = {{ p.CONSTANT_INPUT_POWER|typed }}
    ...

and the parameter in the GSSF-XML is:

    <constant name="CONSTANT_INPUT_POWER" value="140.0" type="float" />

the rendered SIF will be:

    ...
    Power = Real 140.0
    ...

whereas, if the parameter in the GSSF-XML is:

    <constant name="CONSTANT_INPUT_POWER" value="[140.0, 200.0, 120.0]" type="array(float)" />

the rendered SIF will be:

    ...
    Power = Real 140.0 200.0 120.0
    ...

Note that this does not take care of the need to supply an index count to the
power list. A conditional may be needed.
