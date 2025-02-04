# OQpy: Generating OpenQASM 3 + OpenPulse in Python

The goal of `oqpy` ("ock-pie") is to make it easy to generate OpenQASM 3 + OpenPulse in Python. The
`oqpy` library builds off of the [`openqasm3`][openqasm3] and [`openpulse`][openpulse] packages,
which serve as Python reference implementations of the _abstract syntax tree_ (AST) for the
OpenQASM 3 and OpenPulse grammars.

[openqasm3]: https://pypi.org/project/openqasm3/
[openpulse]: https://pypi.org/project/openpulse/

## What are OpenQASM 3 and OpenPulse?

OpenQASM is an imperative programming language designed for near-term quantum computing algorithms
and applications. [OpenQASM 3][openqasm3-docs] extends the original specification by adding support
for classical logic, explicit timing, and pulse-level definitions. The latter is enabled via the use
of [_calibration grammars_][pulses-docs] which allow quantum hardware builders to extend the language
to support hardware-specific directives via `cal` and `defcal` blocks. One such grammar is
[OpenPulse][openpulse-docs], which provides the instructions required for pulse-based control of
many common quantum computing architectures (e.g. superconducting qubits).

[openqasm3-docs]: https://openqasm.com/
[pulses-docs]: https://openqasm.com/language/pulses.html
[openpulse-docs]: https://openqasm.com/language/openpulse.html

## Installation and Getting Started

OQpy can be installed from [PyPI][pypi] or from source in an environment with Python 3.7 or greater.

To install it from PyPI (via `pip`), do the following:

```
pip install oqpy
```

To instead install OQpy from source, do the following from within the repository after cloning it:

```
poetry install
```

Next, check out the following example to get a sense of the kinds of programs we can write with
OQpy.

[pypi]: https://pypi.org/project/oqpy/

## Example: Ramsey Interferometry

A common and useful experiment for qubit characterization is [Ramsey interferometry][ramsey],
which can be used for two purposes: performing a careful measurement of a qubit’s resonant
frequency, and for investigating how long a qubit retains its coherence. In a typical Ramsey
experiment, one varies the length of a delay between the two π/2 pulses, and then measures the state
of the qubit. Below, we'll create a Ramsey interferometry experiment in OpenQASM 3 using OQpy.
As part of this, we’ll use the OpenPulse grammar to allow this experiment to specify its operation
implementations at the calibrated pulse level.

[ramsey]: https://en.wikipedia.org/wiki/Ramsey_interferometry

```python
import oqpy
prog = oqpy.Program()  # create a new oqpy program

# Declare frames: transmon driving frame and readout receive/transmit frames
xy_frame = oqpy.FrameVar(oqpy.PortVar("dac0"), 6.431e9, name="xy_frame")
rx_frame = oqpy.FrameVar(oqpy.PortVar("adc0"), 5.752e9, name="rx_frame")
tx_frame = oqpy.FrameVar(oqpy.PortVar("dac1"), 5.752e9, name="tx_frame")

# Declare the type of waveform we are working with
constant_waveform = oqpy.declare_waveform_generator(
    "constant",
    [("length", oqpy.duration),
     ("amplitude", oqpy.float64)],
)
gaussian_waveform = oqpy.declare_waveform_generator(
    "gaussian",
    [("length", oqpy.duration),
     ("sigma", oqpy.duration),
     ("amplitude", oqpy.float64)],
)

# Provide gate / operation definitions as defcals
qubit = oqpy.PhysicalQubits[1]  # get physical qubit 1

with oqpy.defcal(prog, qubit, "reset"):
    prog.delay(1e-3)  # reset to ground state by waiting 1 ms

with oqpy.defcal(prog, qubit, "measure"):
    prog.play(tx_frame, constant_waveform(2.4e-6, 0.2))
    prog.capture(rx_frame, constant_waveform(2.4e-6, 1))

with oqpy.defcal(prog, qubit, "x90"):
    prog.play(xy_frame, gaussian_waveform(32e-9, 8e-9, 0.2063))

# Loop over shots (i.e. repetitions)
delay_time = oqpy.DurationVar(0, "delay_time")  # initialize a duration
with oqpy.ForIn(prog, range(100), "shot_index"):
    prog.set(delay_time, 0)                     # reset delay time to zero
    # Loop over delays
    with oqpy.ForIn(prog, range(101), "delay_index"):
        (prog.reset(qubit)                      # prepare in ground state
         .gate(qubit, "x90")                    # pi/2 pulse (90° rotation about the x-axis)
         .delay(delay_time, qubit)              # variable delay
         .gate(qubit, "x90")                    # pi/2 pulse (90° rotation about the x-axis)
         .measure(qubit)                        # final measurement
         .increment(delay_time, 100e-9))        # increase delay by 100 ns
```

Running `print(prog.to_qasm(encal_declarations=True))` generates the following OpenQASM:

```qasm3
OPENQASM 3.0;
defcalgrammar "openpulse";
cal {
    extern constant(duration, float[64]) -> waveform;
    extern gaussian(duration, duration, float[64]) -> waveform;
    port dac1;
    port adc0;
    port dac0;
    frame tx_frame = newframe(dac1, 5752000000.0, 0);
    frame rx_frame = newframe(adc0, 5752000000.0, 0);
    frame xy_frame = newframe(dac0, 6431000000.0, 0);
}
duration delay_time = 0.0ns;
defcal reset $1 {
    delay[1000000.0ns];
}
defcal measure $1 {
    play(tx_frame, constant(2400.0ns, 0.2));
    capture(rx_frame, constant(2400.0ns, 1));
}
defcal x90 $1 {
    play(xy_frame, gaussian(32.0ns, 8.0ns, 0.2063));
}
for int shot_index in [0:99] {
    delay_time = 0.0ns;
    for int delay_index in [0:100] {
        reset $1;
        x90 $1;
        delay[delay_time] $1;
        x90 $1;
        measure $1;
        delay_time += 100.0ns;
    }
}
```

## Contributing

We welcome contributions to OQpy including bug fixes, feature requests, etc. To get started, check
out our [contributing guidelines](CONTRIBUTING.md).
