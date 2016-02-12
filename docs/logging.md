# Logging &amp; Errors in GSSF

## Logging tools

### Statistics monitoring

GSSF has prototypal integration with
[vigilant](https://github.com/redbrain/vigilant), a tool that maintains a
datastore monitoring all instances of (in our case)
[go-smart-launcher](go-smart-launcher.md). It can do so across
multiple machines and provides a web-based interface for viewing. Note that this
is entirely distinct from GSSA, which orchestrates workflows such as GSSF, and
is unaware of vigilant monitoring.

Note that *vigilant* has changed name during the Go-Smart project, from
*observant*. This name is often used in the code and will be replaced as the
dependencies are updated. However, as the project is currently *vigilant*, and
seems to be going forward, the comments generally use this name to refer to it.

Monitoring can be configured using the YAML file
*{INSTALLROOT}/etc/gosmart/vigilant.cfg*. Configuration options are as described
in the [vigilant](https://github.com/redbrain/vigilant) documentation.

**TODO**: Update configuration format to JSON, following upstream change.

**FIXME**: Posting vigilant messages on `log_line` is currently suspended, as the filling pipe was slowing the rest of the master process. While this needs to be farmed out to a thread properly, for the moment test this functionality by uncommenting the marked line in logger_vigilant.py.

### Logpick

The logpick functionality allows individual components of the GSSF workflow to
monitor their child process output for certain regular expressions, indicating
the start and end of some internal process. The GoSmartComponent class, on which
all the components are based, will sum the time spent in this internal task
(based on the child's output) and print the total when the subprocess exits. The
logpick entries are expressed as a triple in ``GoSmartComponent.logpick_pairs``:

    ("START_PATTERN", "END_PATTERN", "LABEL")

For example, in the Elmer solver:

    ("CRS_IncompleteLU: ILU(0) (Real), Starting Factorization", "ComputeChange:", "Solver A")

gives, when the solver finally exits,

    Timings (sec resolution):
     --    9 Solver A <'CRS_IncompleteLU: ILU(0) (Real), Starting Factorization' - 'ComputeChange:'>
     --  486 [other]
        ====   
     -- 496

Adding additional logpick entries will, naturally, help account for more of the
time used.

### Rate limiting

Each component has a member ``suppress_logging_over_per_second``, which may be
set to a maximum number of log lines per second from that component or ``None``
to be disabled.

## Error handling

### Exception classes

Very basic unified error types are provided, to help distinguish between user
errors, programmer errors, modeller errors and errors of unknown responsibility.

These contain codes which can be matched by the client-side tools. In theory,
all errors returned from GSSF will be one of these. Any
errors thrown beneath will be caught and wrapped accordingly.

Error Code   | Error ID | Intepretation | GSSF exception class (if app.)
-------------|----------|---------------|---------------------
`SUCCESS`    | 0        | All worked | -
`E_UNKNOWN`  | 1        | Error of unknown origin | `GoSmartError`
`E_CLIENT`   | 2        | Triggered by an issue on the client side, such as illogical input | `GoSmartClientError`
`E_SERVER`   | 3        | Problems with the server or server-side tools | `GoSmartServerError`
`E_MODEL`    | 4        | Modelling problem, where the server cannot complete the task for physical/mathematical/numerical/syntactical reasons that are the responsibility of the model developer | `GoSmartModelError`

In general, we err on the side of caution and attribute anything uncertain to
`E_SERVER` or `E_UNKNOWN`. However, it may be, in the future, that being less
conservative with `E_MODEL` will help provide automatic feedback on issues.

Ideally, in GSSF all errors thrown should be one of the classes listed above,
found in `gssf.errors`. These will be caught by
[go-smart-launcher](go-smart-launcher.md) and an error file written that GSSA
can process and report accordingly. If using GSSF standalone, this will still
work properly.

### Error regexes

Each line is checked for a per-component error regex, and stored as the
subprocess error message if it occurs. Since the subprocess may know nothing
about GSSF, such an approach is required to ensure we can provide some feedback,
at least, if it crashes.
