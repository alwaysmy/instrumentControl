# -*- coding: utf-8 -*-
"""SDS800X HD dual-channel waveform phase-difference measurement.

Pulls C1 (ADPLL DAC out) and C2 (external reference) waveforms over SCPI,
finds rising zero crossings, computes phase difference.
Usage: py sds_phase_meas.py <label>
Writes one line to sds_phase_log.txt: label, f1, f2, phase_deg, phase_std
"""
import sys, time, struct, statistics
import pyvisa

RM = pyvisa.ResourceManager()
SCOPE = 'TCPIP0::192.168.31.220::inst0::INSTR'

def tmc_ascii(inst, cmd):
    inst.write(cmd)
    raw = inst.read_raw()
    # strip TMC header: #N<len><payload>
    if raw[:1] == b'#':
        n = int(raw[1:2])
        ln = int(raw[2:2+n])
        raw = raw[2+n:2+n+ln]
    return raw.decode('latin1')

def wave_ch(inst, ch):
    inst.write(f'WAV:SOUR C{ch}')
    inst.write('WAV:FORM BYTE')
    pre = tmc_ascii(inst, 'WAV:PRE?')
    fields = pre.split(',')
    xinc = float(fields[4]) if len(fields) >= 6 else 1.0
    xorig = float(fields[5]) if len(fields) >= 6 else 0.0
    yinc = float(fields[7]) if len(fields) >= 8 else 1.0
    yorig = float(fields[8]) if len(fields) >= 9 else 0.0
    inst.write('WAV:DAT?')
    raw = inst.read_raw()
    if raw[:1] == b'#':
        n = int(raw[1:2])
        ln = int(raw[2:2+n])
        raw = raw[2+n:2+n+ln]
    ys = [(b - 128 - (yorig / yinc if yinc else 0)) * yinc for b in raw]
    return ys, xinc

def zero_cross_phase(ys1, ys2, xinc, ncycles_avg=20):
    """rising zero crossing times (s) of both, then phase from period fit."""
    def crossings(ys):
        ts = []
        for i in range(1, len(ys)):
            if ys[i-1] < 0 <= ys[i]:
                frac = -ys[i-1] / (ys[i] - ys[i-1])
                ts.append((i - 1 + frac) * xinc)
        return ts
    t1, t2 = crossings(ys1), crossings(ys2)
    if len(t1) < 3 or len(t2) < 3:
        return None, 0.0, 0.0
    per = statistics.median([t1[i+1]-t1[i] for i in range(min(20, len(t1)-1))])
    phis = []
    for tc in t2[:ncycles_avg]:
        # nearest C1 crossing after this C2 crossing
        cand = [x for x in t1 if x >= tc - per]
        if not cand: continue
        dt = cand[0] - tc
        phis.append((dt % per) / per * 360.0)
    if not phis:
        return None, 0.0, 0.0
    m = statistics.median(phis)
    # wrap to [-180,180]
    if m > 180: m -= 360
    sd = statistics.pstdev([min(abs(p-m), 360-abs(p-m)) for p in phis])
    f1 = 1.0 / per
    return m, sd, f1

def main():
    label = sys.argv[1] if len(sys.argv) > 1 else 'run'
    inst = RM.open_resource(SCOPE)
    inst.timeout = 15000
    inst.write('ACQ:WMEM 10000')   # shallow memory: fast transfer
    time.sleep(1.5)                # let it re-acquire
    y1, xi1 = wave_ch(inst, 1)
    y2, xi2 = wave_ch(inst, 2)
    ph, sd, f1 = zero_cross_phase(y1, y2, xi1)
    # C2 freq from its own crossings
    def crossings(ys, xinc):
        ts = []
        for i in range(1, len(ys)):
            if ys[i-1] < 0 <= ys[i]:
                ts.append((i - 1 + ( -ys[i-1])/(ys[i]-ys[i-1])) * xinc)
        return ts
    t2 = crossings(y2, xi2)
    f2 = 1.0/statistics.median([t2[i+1]-t2[i] for i in range(min(20,len(t2)-1))]) if len(t2) > 2 else 0
    line = f"{label}: f1={f1:.2f}Hz f2={f2:.2f}Hz phase={ph:.3f}deg +- {sd:.3f} (n={len(y1)})"
    print(line)
    with open('sds_phase_log.txt', 'a') as fp:
        fp.write(line + '\n')

if __name__ == '__main__':
    main()
