#!/usr/bin/env python3
"""
Pack a phone's UEFI (with the hook that starts the XNU loader) and an optional payload
into an Android boot image for `fastboot boot`.

  kernel = gzip(BootShim + UEFI FD + ["XNUP" container]) + DTB

The boot shim copies the FD to its base and the payload to PAYLOAD_BASE.

The UEFI pieces are taken from a Mu-Silicium tree built here (Mu-Silicium/, see uefi/README.md)
or, when there is none, from devices/<device>/prebuilt/.

usage: mkxnuimg.py [-d device] [-p payload.bin] [-o out.img]

  -d/--device   the device whose UEFI to pack: its <device>Pkg in Mu-Silicium/'s build tree, its
                DTB in Mu-Silicium/Resources/DTBs/<device>.dtb, and its prebuilt/ under
                devices/<device>/. Default: redwood, the reference phone (what this script used
                to be fixed to).
"""
import argparse, gzip, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MU = os.path.join(HERE, 'Mu-Silicium')
DEFAULT_DEVICE = 'redwood'
FD_BASE, FD_SIZE = 0x9FD00000, 0x200000
PAYLOAD_BASE, PAYLOAD_MAX = 0xF0000000, 0x04000000

ap = argparse.ArgumentParser()
ap.add_argument('-d', '--device', default=DEFAULT_DEVICE,
                help=f'the device to pack (default: {DEFAULT_DEVICE}); reads Mu-Silicium/Build/<device>Pkg/ '
                     f'and devices/<device>/prebuilt/')
ap.add_argument('-p', '--payload')
ap.add_argument('-o', '--output', help='the image (default: xnu-<device>.img)')
ap.add_argument('--mode', default='RELEASE')
args = ap.parse_args()

device = args.device
output = args.output or os.path.join(HERE, f'xnu-{device}.img')
PREBUILT = os.path.join(HERE, 'devices', device, 'prebuilt')
fd_path = os.path.join(MU, f'Build/{device}Pkg/{args.mode}_CLANGPDB/FV/SILICIUM_UEFI.fd')
# The FD's base and size are the phone's own (Mu-Silicium's Resources/Configs/<device>.toml, [uefi_fd]); the reference
# phone's are the defaults here, so that a device without one keeps the values this script always used.
fd_base, fd_size = FD_BASE, FD_SIZE
toml = os.path.join(MU, f'Resources/Configs/{device}.toml')
if os.path.isfile(toml):
    try:
        import tomllib
        with open(toml, 'rb') as f:
            cfg = tomllib.load(f).get('uefi_fd', {})
        fd_base = int(cfg.get('base', fd_base))
        fd_size = int(cfg.get('size', fd_size))
        print(f'mkxnuimg.py: {device}: FD {fd_base:#x} + {fd_size:#x} (Resources/Configs/{device}.toml)')
    except Exception as e:                      # a malformed toml is not worth failing the pack over
        print(f'mkxnuimg.py: {device}: cannot read {toml} ({e}); using {fd_base:#x} + {fd_size:#x}', file=sys.stderr)

if os.path.isfile(fd_path):
    shim_dir = os.path.join(MU, 'BootShim')
    for f in ('BootShim.elf', 'BootShim.bin'):
        try: os.unlink(os.path.join(shim_dir, f))
        except FileNotFoundError: pass
    subprocess.check_call(['make', 'REQUIRES_KERNEL_HEADER=1', f'FD_BASE={fd_base:#x}', f'FD_SIZE={fd_size:#x}',
                           f'CFLAGS=--target=aarch64-linux-gnu -DPAYLOAD_BASE={PAYLOAD_BASE:#x}'],
                          cwd=shim_dir, stdout=subprocess.DEVNULL)
    parts = {'shim': os.path.join(shim_dir, 'BootShim.bin'), 'fd': fd_path,
             'dtb': os.path.join(MU, f'Resources/DTBs/{device}.dtb'), 'ramdisk': os.path.join(MU, 'Resources/ramdisk'),
             'mkbootimg': os.path.join(MU, 'Resources/Scripts/mkbootimg.py')}
else:
    parts = {'shim': os.path.join(PREBUILT, 'BootShim.bin'), 'fd': os.path.join(PREBUILT, 'SILICIUM_UEFI.fd'),
             'dtb': os.path.join(PREBUILT, 'device-tree.dtb'), 'ramdisk': os.path.join(PREBUILT, 'ramdisk'),
             'mkbootimg': os.path.join(PREBUILT, 'mkbootimg.py')}
for name, path in parts.items():
    if not os.path.isfile(path):
        hint = ''
        if name == 'fd':
            hint = ("\n  The UEFI image is not in the repository: it carries the phone vendor's own drivers, which are not\n"
                    "  redistributed here. Build it from your own phone's firmware: uefi/README.md")
        elif name == 'dtb' and not os.path.isfile(fd_path):
            hint = f"\n  devices/{device}/prebuilt/ holds this device's prebuilt images; redwood's are the only ones here."
        sys.exit(f'mkxnuimg.py: {path} not found{hint}')
shim = open(parts['shim'], 'rb').read()
fd = open(parts['fd'], 'rb').read()
assert len(fd) == fd_size, f'the FD is {len(fd):#x}, but {device}\'s uefi_fd size is {fd_size:#x}'

blob = shim + fd
if args.payload:
    data = open(args.payload, 'rb').read()
    # the payload file is a complete "XNUP" container (see xnuloader/mkpayload.py)
    assert data[:4] == b'XNUP' and len(data) <= PAYLOAD_MAX - 0x1000, 'bad or oversized payload'
    blob += data
    blob += b'\0' * (-len(blob) % 16)
    print(f'payload: {len(data)} bytes, bytesum={sum(data) & 0xffffffff:08x}')

dtb = open(parts['dtb'], 'rb').read()
kernel = output + '.kernel~'
open(kernel, 'wb').write(gzip.compress(blob, 6) + dtb)
try:
    subprocess.check_call([sys.executable, parts['mkbootimg'], '--kernel', kernel, '--ramdisk', parts['ramdisk'],
                           '--header_version', '1', '-o', output])
finally:
    os.unlink(kernel)
print(f'{output}: {os.path.getsize(output)} bytes (shim {len(shim)}, uncompressed {len(blob)})')
