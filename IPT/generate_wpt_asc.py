#!/usr/bin/env python3
"""Generate an LTspice .asc for 6.78 MHz Series-Series WPT efficiency sweep."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from spicelib import AscEditor
from spicelib.editor.base_schematic import (
    ERotation,
    Line,
    Point,
    SchematicComponent,
    Text,
    TextTypeEnum,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate LTspice ASC for 6.78 MHz WPT efficiency sweep."
    )
    parser.add_argument(
        "--out",
        default="wpt_6p78mhz.asc",
        help="Output ASC file path (default: wpt_6p78mhz.asc)",
    )
    parser.add_argument(
        "--rl-start",
        type=float,
        default=5.0,
        help="RL sweep start in ohm (default: 5)",
    )
    parser.add_argument(
        "--rl-stop",
        type=float,
        default=500.0,
        help="RL sweep stop in ohm (default: 500)",
    )
    parser.add_argument(
        "--rl-step",
        type=float,
        default=5.0,
        help="RL sweep step in ohm (default: 5)",
    )
    return parser


def fmt(value: float) -> str:
    """Format numbers compactly for LTspice directives."""
    return f"{value:.12g}"


def ensure_template(template_path: Path) -> None:
    if template_path.exists():
        return
    template_path.write_text(
        "Version 4.1\n"
        "SHEET 1 1200 800\n"
        "TEXT 32 24 Left 2 !.title 6.78MHz WPT (Series-Series)\n",
        encoding="ascii",
    )


def make_component(
    reference: str,
    symbol: str,
    x: int,
    y: int,
    rotation: ERotation,
    **attributes: str,
) -> SchematicComponent:
    component = SchematicComponent(None, f"SYMBOL {symbol} {x} {y} R0")
    component.reference = reference
    component.symbol = symbol
    component.position = Point(x, y)
    component.rotation = rotation
    component.attributes.update(attributes)
    return component


def add_wire(asc: AscEditor, x1: int, y1: int, x2: int, y2: int) -> None:
    asc.wires.append(Line(Point(x1, y1), Point(x2, y2)))


def add_flag(asc: AscEditor, x: int, y: int, text: str) -> None:
    asc.labels.append(Text(Point(x, y), text, type=TextTypeEnum.LABEL))


def add_directive(asc: AscEditor, x: int, y: int, text: str) -> None:
    asc.directives.append(Text(Point(x, y), text, type=TextTypeEnum.DIRECTIVE))


def generate_with_asc_editor(
    out_path: Path, rl_start: float, rl_stop: float, rl_step: float
) -> None:
    if rl_step <= 0:
        raise ValueError("--rl-step must be > 0")
    if rl_stop <= rl_start:
        raise ValueError("--rl-stop must be greater than --rl-start")

    f = 6.78e6
    v_in = 10.0  # SINE amplitude (Vpk)

    ltx = 16.769762e-6
    lrx = 6.550129e-6
    m = 0.12119597e-6
    qtx = 134.52338
    qrx = 274.71924

    w = 2.0 * math.pi * f
    rtx = w * ltx / qtx
    rrx = w * lrx / qrx
    ctx = 1.0 / (w * w * ltx)
    crx = 1.0 / (w * w * lrx)
    k = m / math.sqrt(ltx * lrx)

    # Transient setup: average efficiency over the last 40 cycles.
    tstop = 120.0 / f
    t1 = 80.0 / f
    t2 = 120.0 / f
    tmax = 1.0 / (f * 200.0)

    template_path = Path(__file__).with_name("wpt_base_template.asc")
    ensure_template(template_path)

    asc = AscEditor(template_path)
    asc.sheet = "1 1200 800"
    asc.components.clear()
    asc.wires.clear()
    asc.labels.clear()
    asc.directives.clear()
    asc.lines.clear()
    asc.shapes.clear()

    # Tx loop: V1 -> Ctx -> Ltx -> ground
    asc.add_component(
        make_component(
            "V1",
            "voltage",
            32,
            112,
            ERotation.R0,
            Value="SINE(0 {VIN} {F})",
            _WINDOW_123=Text(Point(56, 124), "123", 2, TextTypeEnum.ATTRIBUTE),
            _WINDOW_39=Text(Point(0, 0), "39", 0, TextTypeEnum.ATTRIBUTE),
        )
    )
    asc.add_component(
        make_component("Ctx", "cap", 112, 64, ERotation.R270, Value="{CTX}")
    )
    asc.add_component(
        make_component(
            "Ltx",
            "ind",
            256,
            64,
            ERotation.R270,
            Value="{LTX}",
            SpiceLine="Rser={RTX}",
        )
    )

    # Rx loop: floating series loop Lrx -> Crx -> RL -> back to Lrx
    asc.add_component(
        make_component(
            "Lrx",
            "ind",
            560,
            96,
            ERotation.R0,
            Value="{LRX}",
            SpiceLine="Rser={RRX}",
        )
    )
    asc.add_component(
        make_component("Crx", "cap", 688, 64, ERotation.R270, Value="{CRX}")
    )
    asc.add_component(
        make_component("RL1", "res", 848, 96, ERotation.R0, Value="{RL}")
    )

    add_wire(asc, 32, 128, 32, 48)
    add_wire(asc, 112, 48, 32, 48)
    add_wire(asc, 176, 48, 272, 48)
    add_wire(asc, 352, 48, 352, 256)
    add_wire(asc, 32, 256, 32, 208)

    add_wire(asc, 576, 112, 576, 48)
    add_wire(asc, 688, 48, 576, 48)
    add_wire(asc, 752, 48, 864, 48)
    add_wire(asc, 864, 112, 864, 48)
    add_wire(asc, 576, 256, 576, 192)
    add_wire(asc, 864, 256, 864, 192)
    add_wire(asc, 864, 256, 576, 256)

    add_flag(asc, 32, 48, "vin")
    add_flag(asc, 864, 48, "rlp")
    add_flag(asc, 864, 256, "rln")
    add_flag(asc, 32, 256, "0")
    add_flag(asc, 352, 256, "0")

    add_directive(asc, 32, 16, ".title 6.78MHz WPT (Series-Series)")
    add_directive(asc, 32, 296, f".param F={fmt(f)} VIN={fmt(v_in)}")
    add_directive(
        asc,
        32,
        320,
        ".param "
        f"LTX={fmt(ltx)} LRX={fmt(lrx)} M={fmt(m)} QTX={fmt(qtx)} QRX={fmt(qrx)}",
    )
    add_directive(
        asc,
        32,
        344,
        ".param "
        f"RTX={fmt(rtx)} RRX={fmt(rrx)} CTX={fmt(ctx)} CRX={fmt(crx)} K={fmt(k)} RL={fmt(rl_start)}",
    )
    add_directive(asc, 32, 368, f".tran 0 {fmt(tstop)} 0 {fmt(tmax)}")
    add_directive(
        asc,
        32,
        392,
        f".step param RL {fmt(rl_start)} {fmt(rl_stop)} {fmt(rl_step)}",
    )
    add_directive(
        asc,
        32,
        416,
        f".meas tran Pin AVG -V(vin)*I(V1) from {fmt(t1)} to {fmt(t2)}",
    )
    add_directive(
        asc,
        32,
        440,
        f".meas tran Pout AVG V(rlp,rln)*I(RL1) from {fmt(t1)} to {fmt(t2)}",
    )
    add_directive(asc, 32, 464, ".meas tran Eff PARAM 100*Pout/Pin")
    add_directive(asc, 32, 488, "K1 Ltx Lrx {K}")
    asc.save_netlist(out_path)


def main() -> None:
    args = build_parser().parse_args()
    out_path = Path(args.out)
    generate_with_asc_editor(out_path, args.rl_start, args.rl_stop, args.rl_step)
    print(f"Generated: {out_path.resolve()}")


if __name__ == "__main__":
    main()
