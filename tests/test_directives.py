############################################################################
#  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License").
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
############################################################################

import copy
import textwrap
from dataclasses import dataclass

import numpy as np
import pytest
from openpulse.printer import dumps

from oqpy import *
from oqpy.base import expr_matches
from oqpy.quantum_types import PhysicalQubits
from oqpy.timing import OQDurationLiteral


def test_version_string():
    prog = Program(version="2.9")

    with pytest.raises(RuntimeError):
        prog = Program("2.x")

    expected = textwrap.dedent(
        """
        OPENQASM 2.9;
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_variable_declaration():
    b = BoolVar(True, "b")
    i = IntVar(-4, "i")
    u = UintVar(5, "u")
    x = DurationVar(100e-9, "blah")
    y = FloatVar[50](3.3, "y")
    ang = AngleVar(name="ang")
    arr = BitVar[20](name="arr")
    c = BitVar(name="c")
    vars = [b, i, u, x, y, ang, arr, c]

    prog = Program(version=None)
    prog.declare(vars)
    prog.set(arr[1], 0)

    with pytest.raises(IndexError):
        prog.set(arr[40], 2)
    with pytest.raises(ValueError):
        BitVar[2.1](name="d")
    with pytest.raises(ValueError):
        BitVar[0](name="d")
    with pytest.raises(ValueError):
        BitVar[-1](name="d")
    with pytest.raises(IndexError):
        prog.set(arr[1.3], 0)
    with pytest.raises(TypeError):
        prog.set(c[0], 1)

    expected = textwrap.dedent(
        """
        bool b = true;
        int[32] i = -4;
        uint[32] u = 5;
        duration blah = 100.0ns;
        float[50] y = 3.3;
        angle[32] ang;
        bit[20] arr;
        bit c;
        arr[1] = 0;
        """
    ).strip()

    assert isinstance(arr[14], BitVar)
    assert prog.to_qasm() == expected


def test_complex_numbers_declaration():
    vars = [
        ComplexVar(name="z"),
        ComplexVar(1 + 0j, name="z1"),
        ComplexVar(-1 + 0j, name="z2"),
        ComplexVar(0 + 2j, name="z3"),
        ComplexVar(0 - 2j, name="z4"),
        ComplexVar(1 + 2j, name="z5"),
        ComplexVar(1 - 2j, name="z6"),
        ComplexVar(-1 + 2j, name="z7"),
        ComplexVar(-1 - 2j, name="z8"),
        ComplexVar(1, name="z9"),
        ComplexVar(-1, name="z10"),
        ComplexVar(2j, name="z11"),
        ComplexVar(-2j, name="z12"),
        ComplexVar[float32](1.2 - 2.1j, name="z_with_type1"),
        ComplexVar[float_(16)](1.2 - 2.1j, name="z_with_type2"),
        ComplexVar(1.2 - 2.1j, base_type=float_(16), name="z_with_type3"),
    ]
    with pytest.raises(AssertionError):
        ComplexVar(-2j, base_type=IntVar, name="z12")

    prog = Program(version=None)
    prog.declare(vars)

    expected = textwrap.dedent(
        """
        complex[float[64]] z;
        complex[float[64]] z1 = 1.0;
        complex[float[64]] z2 = -1.0;
        complex[float[64]] z3 = 2.0im;
        complex[float[64]] z4 = -2.0im;
        complex[float[64]] z5 = 1.0 + 2.0im;
        complex[float[64]] z6 = 1.0 - 2.0im;
        complex[float[64]] z7 = -1.0 + 2.0im;
        complex[float[64]] z8 = -1.0 - 2.0im;
        complex[float[64]] z9 = 1.0;
        complex[float[64]] z10 = -1.0;
        complex[float[64]] z11 = 2.0im;
        complex[float[64]] z12 = -2.0im;
        complex[float[32]] z_with_type1 = 1.2 - 2.1im;
        complex[float[16]] z_with_type2 = 1.2 - 2.1im;
        complex[float[16]] z_with_type3 = 1.2 - 2.1im;
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_non_trivial_variable_declaration():
    prog = Program()
    z1 = ComplexVar(5, "z1")
    z2 = ComplexVar(2 * z1, "z2")
    z3 = ComplexVar(z2 + 2j, "z3")
    vars = [z1, z2, z3]
    prog.declare(vars)

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        complex[float[64]] z1 = 5.0;
        complex[float[64]] z2 = 2 * z1;
        complex[float[64]] z3 = z2 + 2.0im;
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_variable_assignment():
    prog = Program()
    i = IntVar(5, name="i")
    prog.set(i, 8)
    prog.set(i.to_ast(prog), 1)
    prog.increment(i, 3)
    prog.mod_equals(i, 2)

    with pytest.raises(TypeError):
        prog.set(i, None)

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        int[32] i = 5;
        i = 8;
        i = 1;
        i += 3;
        i %= 2;
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_binary_expressions():
    prog = Program()
    i = IntVar(5, "i")
    j = IntVar(2, "j")
    prog.set(i, 2 * (i + j))
    prog.set(j, 2 % (2 + i) % 2)

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        int[32] i = 5;
        int[32] j = 2;
        i = 2 * (i + j);
        j = 2 % (2 + i) % 2;
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_measure_reset():
    prog = Program()
    q = PhysicalQubits[0]
    c = BitVar(name="c")
    prog.reset(q)
    prog.measure(q, c)
    prog.measure(q)

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        bit c;
        reset $0;
        c = measure $0;
        measure $0;
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_bare_if():
    prog = Program()
    i = IntVar(3, "i")
    with If(prog, i <= 0):
        prog.increment(i, 1)
    with If(prog, i != 0):
        prog.set(i, 0)
    with pytest.raises(RuntimeError):
        with If(prog, i < 0 or i == 0):
            prog.increment(i, 1)

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        int[32] i = 3;
        if (i <= 0) {
            i += 1;
        }
        if (i != 0) {
            i = 0;
        }
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_if_else():
    prog = Program()
    i = IntVar(3, "i")
    j = IntVar(2, "j")
    with If(prog, i >= 0):
        with If(prog, j == 0):
            prog.increment(i, 1)
        with Else(prog):
            prog.decrement(i, 1)
    with Else(prog):
        prog.decrement(i, 1)

    with pytest.raises(RuntimeError):
        with Else(prog):
            prog.decrement(i, 1)

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        int[32] i = 3;
        int[32] j = 2;
        if (i >= 0) {
            if (j == 0) {
                i += 1;
            } else {
                i -= 1;
            }
        } else {
            i -= 1;
        }
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_for_in():
    prog = Program()
    j = IntVar(0, "j")
    wf = WaveformVar([0.1, -1.2, 1.3, 2.4], name="wf")
    with ForIn(prog, range(5), "i") as i:
        prog.increment(j, i)
    with ForIn(prog, [-1, 1, -1, 1], "k") as k:
        prog.decrement(j, k)
    with ForIn(prog, np.array([0, 3]), "l") as l:
        prog.set(j, l)
    with ForIn(prog, wf, "m") as m:
        prog.set(j, m)

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        int[32] j = 0;
        waveform wf = {0.1, -1.2, 1.3, 2.4};
        for int i in [0:4] {
            j += i;
        }
        for int k in {-1, 1, -1, 1} {
            j -= k;
        }
        for int l in {0, 3} {
            j = l;
        }
        for int m in wf {
            j = m;
        }
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_while():
    prog = Program()
    j = IntVar(0, "j")
    with While(prog, j < 5):
        prog.increment(j, 1)
    with While(prog, j > 0):
        prog.decrement(j, 1)

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        int[32] j = 0;
        while (j < 5) {
            j += 1;
        }
        while (j > 0) {
            j -= 1;
        }
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_create_frame():
    prog = Program()
    port = PortVar("storage")
    storage_frame = FrameVar(port, 6e9, name="storage_frame")
    readout_frame = FrameVar(name="readout_frame")
    prog.declare([storage_frame, readout_frame])

    with pytest.raises(ValueError):
        frame = FrameVar(port, name="storage_frame")

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        port storage;
        frame storage_frame = newframe(storage, 6000000000.0, 0);
        frame readout_frame;
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_subroutine_with_return():
    prog = Program()

    @subroutine
    def multiply(prog: Program, x: IntVar, y: IntVar) -> IntVar:
        return x * y

    y = IntVar(2, "y")
    prog.set(y, multiply(prog, y, 3))

    @subroutine
    def declare(prog: Program, x: IntVar):
        prog.declare([x])

    declare(prog, y)

    @subroutine
    def delay50ns(prog: Program, q: Qubit) -> None:
        prog.delay(50e-9, q)

    q = PhysicalQubits[0]
    delay50ns(prog, q)

    with pytest.raises(ValueError):

        @subroutine
        def return1(prog: Program) -> float:
            return 1.0

        return1(prog)

    with pytest.raises(ValueError):

        @subroutine
        def add(prog: Program, x: IntVar, y) -> IntVar:
            return x + y

        prog.set(y, add(prog, y, 3))

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        def multiply(int[32] x, int[32] y) -> int[32] {
            return x * y;
        }
        int[32] y = 2;
        y = multiply(y, 3);
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_box_and_timings():
    constant = declare_waveform_generator("constant", [("length", duration), ("iq", complex128)])

    port = PortVar("portname")
    frame = FrameVar(port, 1e9, name="framename")
    prog = Program()
    with Box(prog, 500e-9):
        prog.play(frame, constant(100e-9, 0.5))
        prog.delay(frame, 200e-7)
        prog.play(frame, constant(100e-9, 0.5))

    with Box(prog):
        prog.play(frame, constant(200e-9, 0.5))

    with pytest.raises(TypeError):
        f = FloatVar(200e-9, "f", needs_declaration=False)
        make_duration(f.to_ast(prog))

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        extern constant(duration, complex[float[64]]) -> waveform;
        port portname;
        frame framename = newframe(portname, 1000000000.0, 0);
        box[500.0ns] {
            play(framename, constant(100.0ns, 0.5));
            delay[framename] 2e-05;
            play(framename, constant(100.0ns, 0.5));
        }
        box {
            play(framename, constant(200.0ns, 0.5));
        }
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_play_capture():
    port = PortVar("portname")
    frame = FrameVar(port, 1e9, name="framename")
    prog = Program()
    constant = declare_waveform_generator("constant", [("length", duration), ("iq", complex128)])

    prog.play(frame, constant(1e-6, 0.5))
    kernel = WaveformVar(constant(1e-6, iq=1), "kernel")
    prog.capture(frame, kernel)

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        extern constant(duration, complex[float[64]]) -> waveform;
        port portname;
        frame framename = newframe(portname, 1000000000.0, 0);
        waveform kernel = constant(1000.0ns, 1);
        play(framename, constant(1000.0ns, 0.5));
        capture(framename, kernel);
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_set_shift_frequency():
    port = PortVar("portname")
    frame = FrameVar(port, 1e9, name="framename")
    prog = Program()

    prog.set_frequency(frame, 1.1e9)
    prog.shift_frequency(frame, 0.2e9)

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        port portname;
        frame framename = newframe(portname, 1000000000.0, 0);
        set_frequency(framename, 1100000000.0);
        shift_frequency(framename, 200000000.0);
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_ramsey_example():
    prog = Program()
    constant = declare_waveform_generator("constant", [("length", duration), ("iq", complex128)])
    gaussian = declare_waveform_generator(
        "gaussian",
        [("length", duration), ("sigma", duration), ("amplitude", float64), ("phase", float64)],
    )
    tx_waveform = constant(2.4e-6, 0.2)

    q_port = PortVar("q_port")
    rx_port = PortVar("rx_port")
    tx_port = PortVar("tx_port")
    ports = [q_port, rx_port, tx_port]

    q_frame = FrameVar(q_port, 6.431e9, name="q_frame")
    rx_frame = FrameVar(rx_port, 5.752e9, name="rx_frame")
    tx_frame = FrameVar(tx_port, 5.752e9, name="tx_frame")
    frames = [q_frame, rx_frame, tx_frame]

    with Cal(prog):
        prog.declare(ports)
        prog.declare(frames)

    q2 = PhysicalQubits[2]

    with defcal(prog, q2, "readout"):
        prog.play(tx_frame, tx_waveform)
        prog.capture(rx_frame, constant(2.4e-6, 1))

    with defcal(prog, q2, "x90"):
        prog.play(q_frame, gaussian(32e-9, 8e-9, 0.2063, 0.0))

    ramsey_delay = DurationVar(12e-6, "ramsey_delay")
    tppi_angle = AngleVar(0, "tppi_angle")

    with Cal(prog):
        with ForIn(prog, range(1001), "shot") as shot:
            prog.declare(ramsey_delay)
            prog.declare(tppi_angle)
            with ForIn(prog, range(81), "delay_increment") as delay_increment:
                (
                    prog.delay(100e-6)
                    .set_phase(q_frame, 0)
                    .set_phase(rx_frame, 0)
                    .set_phase(tx_frame, 0)
                    .gate(q2, "x90")
                    .delay(ramsey_delay)
                    .shift_phase(q_frame, tppi_angle)
                    .gate(q2, "x90")
                    .gate(q2, "readout")
                    .increment(tppi_angle, 20e-9 * 5e6 * 2 * np.pi)
                    .increment(ramsey_delay, 20e-9)
                )

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        extern constant(duration, complex[float[64]]) -> waveform;
        extern gaussian(duration, duration, float[64], float[64]) -> waveform;
        cal {
            port q_port;
            port rx_port;
            port tx_port;
            frame q_frame = newframe(q_port, 6431000000.0, 0);
            frame rx_frame = newframe(rx_port, 5752000000.0, 0);
            frame tx_frame = newframe(tx_port, 5752000000.0, 0);
        }
        defcal readout $2 {
            play(tx_frame, constant(2400.0ns, 0.2));
            capture(rx_frame, constant(2400.0ns, 1));
        }
        defcal x90 $2 {
            play(q_frame, gaussian(32.0ns, 8.0ns, 0.2063, 0.0));
        }
        cal {
            for int shot in [0:1000] {
                duration ramsey_delay = 12000.0ns;
                angle[32] tppi_angle = 0;
                for int delay_increment in [0:80] {
                    delay[100000.0ns];
                    set_phase(q_frame, 0);
                    set_phase(rx_frame, 0);
                    set_phase(tx_frame, 0);
                    x90 $2;
                    delay[ramsey_delay];
                    shift_phase(q_frame, tppi_angle);
                    x90 $2;
                    readout $2;
                    tppi_angle += 0.6283185307179586;
                    ramsey_delay += 20.0ns;
                }
            }
        }
        """
    ).strip()

    expect_defcal_x90_q2 = textwrap.dedent(
        """
        defcal x90 $2 {
            play(q_frame, gaussian(32.0ns, 8.0ns, 0.2063, 0.0));
        }
        """
    ).strip()

    expect_defcal_readout_q2 = textwrap.dedent(
        """
        defcal readout $2 {
            play(tx_frame, constant(2400.0ns, 0.2));
            capture(rx_frame, constant(2400.0ns, 1));
        }
        """
    ).strip()

    assert prog.to_qasm() == expected
    assert dumps(prog.defcals[("$2", "x90")], indent="    ").strip() == expect_defcal_x90_q2
    assert dumps(prog.defcals[("$2", "readout")], indent="    ").strip() == expect_defcal_readout_q2


def test_rabi_example():
    prog = Program()
    constant = declare_waveform_generator("constant", [("length", duration), ("iq", complex128)])
    gaussian = declare_waveform_generator(
        "gaussian",
        [("length", duration), ("sigma", duration), ("amplitude", float64), ("phase", float64)],
    )

    zcu216_dac231_0 = PortVar("zcu216_dac231_0")
    zcu216_dac230_0 = PortVar("zcu216_dac230_0")
    zcu216_adc225_0 = PortVar("zcu216_adc225_0")
    q0_transmon_xy_frame = FrameVar(zcu216_dac231_0, 3911851971.26885, name="q0_transmon_xy_frame")
    q0_readout_tx_frame = FrameVar(zcu216_dac230_0, 3571600000, name="q0_readout_tx_frame")
    q0_readout_rx_frame = FrameVar(zcu216_adc225_0, 3571600000, name="q0_readout_rx_frame")
    frames = [q0_transmon_xy_frame, q0_readout_tx_frame, q0_readout_rx_frame]
    rabi_pulse_wf = WaveformVar(gaussian(5.2e-8, 1.3e-8, 1.0, 0.0), "rabi_pulse_wf")
    readout_waveform_wf = WaveformVar(constant(1.6e-6, 0.02), "readout_waveform_wf")
    readout_kernel_wf = WaveformVar(constant(1.6e-6, 1), "readout_kernel_wf")
    with ForIn(prog, range(1, 1001), "shot") as shot:
        prog.set_scale(q0_transmon_xy_frame, -0.2)
        with ForIn(prog, range(1, 102), "amplitude") as amplitude:
            prog.delay(200e-6, frames)
            for frame in frames:
                prog.set_phase(frame, 0)
            (
                prog.play(q0_transmon_xy_frame, rabi_pulse_wf)
                .barrier(frames)
                .play(q0_readout_tx_frame, readout_waveform_wf)
                .capture(q0_readout_rx_frame, readout_kernel_wf)
                .barrier(frames)
                .shift_scale(q0_transmon_xy_frame, 0.4 / 100)
            )

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        cal {
            port zcu216_adc225_0;
            port zcu216_dac230_0;
            port zcu216_dac231_0;
            frame q0_transmon_xy_frame = newframe(zcu216_dac231_0, 3911851971.26885, 0);
            frame q0_readout_tx_frame = newframe(zcu216_dac230_0, 3571600000, 0);
            frame q0_readout_rx_frame = newframe(zcu216_adc225_0, 3571600000, 0);
            waveform rabi_pulse_wf = gaussian(52.0ns, 13.0ns, 1.0, 0.0);
            waveform readout_waveform_wf = constant(1600.0ns, 0.02);
            waveform readout_kernel_wf = constant(1600.0ns, 1);
            for int shot in [1:1000] {
                set_scale(q0_transmon_xy_frame, -0.2);
                for int amplitude in [1:101] {
                    delay[200000.0ns] q0_transmon_xy_frame, q0_readout_tx_frame, q0_readout_rx_frame;
                    set_phase(q0_transmon_xy_frame, 0);
                    set_phase(q0_readout_tx_frame, 0);
                    set_phase(q0_readout_rx_frame, 0);
                    play(q0_transmon_xy_frame, rabi_pulse_wf);
                    barrier q0_transmon_xy_frame, q0_readout_tx_frame, q0_readout_rx_frame;
                    play(q0_readout_tx_frame, readout_waveform_wf);
                    capture(q0_readout_rx_frame, readout_kernel_wf);
                    barrier q0_transmon_xy_frame, q0_readout_tx_frame, q0_readout_rx_frame;
                    shift_scale(q0_transmon_xy_frame, 0.004);
                }
            }
        }
        """
    ).strip()

    assert prog.to_qasm(encal=True, include_externs=False) == expected


def test_program_add():
    prog1 = Program()
    constant = declare_waveform_generator("constant", [("length", duration), ("iq", complex128)])

    prog1.delay(1e-6)

    prog2 = Program()
    q1 = PhysicalQubits[1]
    port = PortVar("p1")
    frame = FrameVar(port, 5e9, name="f1")
    wf = WaveformVar(constant(100e-9, 0.5), "wf")
    with defcal(prog2, q1, "x180"):
        prog2.play(frame, wf)
    prog2.gate(q1, "x180")
    i = IntVar(5, "i")
    prog2.declare(i)

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        extern constant(duration, complex[float[64]]) -> waveform;
        port p1;
        frame f1 = newframe(p1, 5000000000.0, 0);
        waveform wf = constant(100.0ns, 0.5);
        delay[1000.0ns];
        defcal x180 $1 {
            play(f1, wf);
        }
        x180 $1;
        int[32] i = 5;
        """
    ).strip()

    prog = prog1 + prog2
    assert prog.to_qasm() == expected

    with pytest.raises(RuntimeError):
        with If(prog2, i == 0):
            prog = prog1 + prog2


def test_expression_convertible():
    @dataclass
    class A:
        name: str

        def _to_oqpy_expression(self):
            return DurationVar(1e-7, self.name)

    frame = FrameVar(name="f1")
    prog = Program()
    prog.set(A("a1"), 2)
    prog.delay(A("a2"), frame)
    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        duration a1 = 100.0ns;
        duration a2 = 100.0ns;
        frame f1;
        a1 = 2;
        delay[a2] f1;
        """
    ).strip()
    assert prog.to_qasm() == expected


def test_waveform_extern_arg_passing():
    prog = Program()
    constant = declare_waveform_generator("constant", [("length", duration), ("iq", complex128)])
    port = PortVar("p1")
    frame = FrameVar(port, 5e9, name="f1")
    prog.play(frame, constant(10e-9, 0.1))
    prog.play(frame, constant(20e-9, iq=0.2))
    prog.play(frame, constant(length=40e-9, iq=0.4))
    prog.play(frame, constant(iq=0.5, length=50e-9))
    with pytest.raises(TypeError):
        prog.play(frame, constant(10e-9, length=10e-9))
    with pytest.raises(TypeError):
        prog.play(frame, constant(10e-9, blah=10e-9))
    with pytest.raises(TypeError):
        prog.play(frame, constant(10e-9, 0.1, 0.1))

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        extern constant(duration, complex[float[64]]) -> waveform;
        port p1;
        frame f1 = newframe(p1, 5000000000.0, 0);
        play(f1, constant(10.0ns, 0.1));
        play(f1, constant(20.0ns, 0.2));
        play(f1, constant(40.0ns, 0.4));
        play(f1, constant(50.0ns, 0.5));
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_needs_declaration():
    prog = Program()
    i1 = IntVar(1, name="i1")
    i2 = IntVar(name="i2", needs_declaration=False)
    p1 = PortVar("p1")
    p2 = PortVar("p2", needs_declaration=False)
    f1 = FrameVar(p1, 5e9, name="f1")
    f2 = FrameVar(p2, 5e9, name="f2", needs_declaration=False)
    q1 = Qubit("q1")
    q2 = Qubit("q2", needs_declaration=False)
    prog.increment(i1, 1)
    prog.increment(i2, 1)
    prog.set_phase(f1, 0)
    prog.set_phase(f2, 0)
    prog.gate(q1, "X")
    prog.gate(q2, "X")

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        port p1;
        int[32] i1 = 1;
        frame f1 = newframe(p1, 5000000000.0, 0);
        qubit q1;
        i1 += 1;
        i2 += 1;
        set_phase(f1, 0);
        set_phase(f2, 0);
        X q1;
        X q2;
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_discrete_waveform():
    port = PortVar("port")
    frame = FrameVar(port, 5e9, name="frame")
    wfm_float = WaveformVar([-1.2, 1.5, 0.1, 0], name="wfm_float")
    wfm_int = WaveformVar((1, 0, 4, -1), name="wfm_int")
    wfm_complex = WaveformVar(
        np.array([1 + 2j, -1.2j + 3.2, -2.1j, complex(1, 0)]), name="wfm_complex"
    )
    wfm_notype = WaveformVar([0.0, -1j + 0, 1.2 + 0j, -1], name="wfm_notype")

    prog = Program()
    prog.declare([wfm_float, wfm_int, wfm_complex, wfm_notype])
    prog.play(frame, wfm_complex)
    prog.play(frame, [1] * 2 + [0] * 2)

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        port port;
        frame frame = newframe(port, 5000000000.0, 0);
        waveform wfm_float = {-1.2, 1.5, 0.1, 0};
        waveform wfm_int = {1, 0, 4, -1};
        waveform wfm_complex = {1.0 + 2.0im, 3.2 - 1.2im, -2.1im, 1.0};
        waveform wfm_notype = {0.0, -1.0im, 1.2, -1};
        play(frame, wfm_complex);
        play(frame, {1, 1, 0, 0});
        """
    ).strip()

    assert prog.to_qasm() == expected


def test_var_and_expr_matches():
    p1 = PortVar("p1")
    p2 = PortVar("p2")
    f1 = FrameVar(p1, 5e9, name="f1")
    assert f1._var_matches(f1)
    assert f1._var_matches(copy.deepcopy(f1))

    assert expr_matches(f1, f1)
    assert not expr_matches(f1, p1)
    assert not expr_matches(f1, FrameVar(p1, 4e9, name="frame"))
    assert not expr_matches(f1, FrameVar(p2, 5e9, name="frame"))
    assert not expr_matches(BitVar[2]([1, 2], name="a"), BitVar[2]([1], name="a"))

    prog = Program()
    prog.declare(p1)
    assert expr_matches(prog.declared_vars, {"p1": p1})
    assert not expr_matches(prog.declared_vars, {"p2": p1})


def test_program_tracks_frame_waveform_vars():
    prog = Program()

    p1 = PortVar("p1")
    p2 = PortVar("p2")
    p3 = PortVar("p3")
    ports = [p1, p2, p3]

    f1 = FrameVar(p1, 6.431e9, name="f1")
    f2 = FrameVar(p2, 5.752e9, name="f2")

    constant = declare_waveform_generator("constant", [("length", duration), ("iq", complex128)])
    constant_wf = WaveformVar(constant(1.6e-6, 0.02), "constant_wf")

    # No FrameVar or WaveformVar used in the program yet
    assert expr_matches(list(prog.frame_vars), [])
    assert expr_matches(list(prog.waveform_vars), [])

    with Cal(prog):
        prog.declare(ports)
        # add declared vars for FrameVar and WaveformVar
        prog.declare(f1)
        prog.declare(constant_wf)

    q1 = PhysicalQubits[1]

    with defcal(prog, q1, "readout"):
        # use undeclared FrameVar and WaveformVar
        f3 = FrameVar(p3, 5.752e9, name="f3")
        discrete_wf = WaveformVar([-1.2, 1.5, 0.1, 0], name="discrete_wf")
        prog.play(f3, discrete_wf)
        # in-line waveforms will not be tracked by the program
        prog.capture(f2, constant(2.4e-6, 1))

    assert expr_matches(list(prog.frame_vars), [f1, f3, f2])
    assert expr_matches(list(prog.waveform_vars), [constant_wf, discrete_wf])


def test_make_duration():
    assert expr_matches(make_duration(1e-3), OQDurationLiteral(1e-3))
    assert expr_matches(make_duration(OQDurationLiteral(1e-4)), OQDurationLiteral(1e-4))

    class MyExprConvertible:
        def _to_oqpy_expression(self):
            return OQDurationLiteral(1e-5)

    assert expr_matches(make_duration(MyExprConvertible()), OQDurationLiteral(1e-5))

    class MyToAst:
        def to_ast(self):
            return OQDurationLiteral(1e-6)

    obj = MyToAst()
    assert make_duration(obj) is obj

    with pytest.raises(TypeError):
        make_duration("asdf")


def test_autoencal():
    port = PortVar("portname")
    frame = FrameVar(port, 1e9, name="framename")
    prog = Program()
    constant = declare_waveform_generator("constant", [("length", duration), ("iq", complex128)])
    i = IntVar(0, "i")

    prog.increment(i, 1)
    with Cal(prog):
        prog.play(frame, constant(1e-6, 0.5))
        kernel = WaveformVar(constant(1e-6, iq=1), "kernel")
        prog.capture(frame, kernel)

    expected = textwrap.dedent(
        """
        OPENQASM 3.0;
        defcalgrammar "openpulse";
        cal {
            extern constant(duration, complex[float[64]]) -> waveform;
            port portname;
            frame framename = newframe(portname, 1000000000.0, 0);
            waveform kernel = constant(1000.0ns, 1);
        }
        int[32] i = 0;
        i += 1;
        cal {
            play(framename, constant(1000.0ns, 0.5));
            capture(framename, kernel);
        }
        """
    ).strip()

    assert prog.to_qasm(encal_declarations=True) == expected


def test_ramsey_example_blog():
    import oqpy

    ramsey_prog = oqpy.Program()                    # create a new oqpy program
    qubit = oqpy.PhysicalQubits[1]                  # get physical qubit 1
    delay_time = oqpy.DurationVar(0, "delay_time")  # initialize a duration

    # Loop over shots (i.e. repetitions)
    with oqpy.ForIn(ramsey_prog, range(100), "shot_index"):
        ramsey_prog.set(delay_time, 0)              # reset delay time to zero
        # Loop over delays
        with oqpy.ForIn(ramsey_prog, range(101), "delay_index"):
            (ramsey_prog.reset(qubit)               # prepare in ground state
             .gate(qubit, "x90")                    # pi/2 pulse
             .delay(delay_time, qubit)              # variable delay
             .gate(qubit, "x90")                    # pi/2 pulse
             .measure(qubit)                        # final measurement
             .increment(delay_time, 100e-9))        # increase delay by 100 ns

    defcals_prog = oqpy.Program()   # create a new oqpy program
    qubit = oqpy.PhysicalQubits[1]  # get physical qubit 1

    # Declare frames: transmon driving frame and readout receive/transmit frames
    xy_frame = oqpy.FrameVar(oqpy.PortVar("dac0"), 6.431e9, name="xy_frame")
    rx_frame = oqpy.FrameVar(oqpy.PortVar("adc0"), 5.752e9, name="rx_frame")
    tx_frame = oqpy.FrameVar(oqpy.PortVar("dac1"), 5.752e9, name="tx_frame")

    # Declare the type of waveform we are working with.
    # It is up to the backend receiving the openqasm to specify
    # what waveforms are allowed. The waveform names and argument types
    # will therefore need to coordinate with the backend.
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

    with oqpy.defcal(defcals_prog, qubit, "reset"):
        defcals_prog.delay(1e-3)  # reset to ground state by waiting 1 millisecond

    with oqpy.defcal(defcals_prog, qubit, "measure"):
        defcals_prog.play(tx_frame, constant_waveform(2.4e-6, 0.2))
        defcals_prog.capture(rx_frame, constant_waveform(2.4e-6, 1))

    with oqpy.defcal(defcals_prog, qubit, "x90"):
        defcals_prog.play(xy_frame, gaussian_waveform(32e-9, 8e-9, 0.2063))

    full_prog = defcals_prog + ramsey_prog

    expected = textwrap.dedent(
        """
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
        """
    ).strip()

    assert full_prog.to_qasm(encal_declarations=True) == expected
