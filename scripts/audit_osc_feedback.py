#!/usr/bin/env python3
"""Static audit for XMSeries-MCP OSC execution-feedback safety.

Read-only checks for the server's own OSC contracts:
- immediate fader/mute/send writes use transactional readback;
- transactional writes re-read the same OSC address and detect disconnects;
- ramp automation verifies its final value;
- known raw/bulk exceptions remain explicitly visible until hardened.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OSC_CLIENT = ROOT / "src" / "osc-client.ts"
AUTOMATION = ROOT / "src" / "automation.ts"
INDEX = ROOT / "src" / "index.ts"

REQUIRED_OSC_CLIENT = {
    "transactional write entry": "async writeAndVerify(address: string, args: any[]",
    "same-address readback": "actual = await this.sendAndReceive(address)",
    "disconnect on failed readback": "impossible de confirmer l'ecriture OSC",
    "channel fader verified": "await this.writeLevelAndVerify(path, level, { label: `channel ${channel} fader` });",
    "channel mute verified": "await this.writeAndVerify(path, [mute ? 0 : 1]",
    "channel send verified": "await this.writeLevelAndVerify(path, level, { label: `channel ${channel} send to bus ${bus}` });",
}

REQUIRED_AUTOMATION = {
    "ramp final verification": "await this.verifyRampFinalValue(job, action, clamp01(to));",
    "ramp final readback": "actual = await action.read();",
}

KNOWN_EXCEPTIONS = {
    "delayed raw preflight plus unverified send": (
        "await osc.assertMixerOnline();",
        "await osc.sendRaw(command.address, args, { allowOfflineWrite: true });",
    ),
    "raw ramp intermediate unchecked send": (
        "write: (level) => osc.sendRaw(writeAddress, [coerceOscArg(level, target.osctype || \"float\")], { allowOfflineWrite: true })",
    ),
    "bulk includeMain unchecked fader": "await osc.setFaderUnchecked(channel, converted.level);",
}


def present(text: str, needle) -> bool:
    if isinstance(needle, tuple):
        return all(part in text for part in needle)
    return needle in text


def main() -> int:
    files = [OSC_CLIENT, AUTOMATION, INDEX]
    missing = [p for p in files if not p.is_file()]
    if missing:
        for path in missing:
            print(f"OSC_FEEDBACK FAIL missing {path}")
        return 2

    osc_client = OSC_CLIENT.read_text(encoding="utf-8")
    automation = AUTOMATION.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")

    ok = True
    for label, snippet in REQUIRED_OSC_CLIENT.items():
        found = snippet in osc_client
        print(f"OSC_FEEDBACK {'OK' if found else 'FAIL'} {label}")
        ok = ok and found
    for label, snippet in REQUIRED_AUTOMATION.items():
        found = snippet in automation
        print(f"OSC_FEEDBACK {'OK' if found else 'FAIL'} {label}")
        ok = ok and found

    for label, needle in KNOWN_EXCEPTIONS.items():
        found = present(index, needle)
        print(f"OSC_FEEDBACK {'WARN' if found else 'OK'} {label}{' still present' if found else ' not detected'}")

    if not ok:
        print("OSC feedback audit FAILED")
        return 1

    print("OSC feedback audit OK: core immediate writes and ramp final state are verified; WARN lines identify server-local exceptions still to harden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
