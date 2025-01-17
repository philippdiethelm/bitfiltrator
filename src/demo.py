import argparse
from pathlib import Path

import resources
from bit_locator import BitLocator
from bitstream import Bitstream
from device_summary import DeviceSummary
from frame import ConfigFrame, FrameAddressRegister


def extract_frames(
  bitstream: Bitstream,
  dev_summary: DeviceSummary
) -> dict[
  tuple[
    str, # SLR name
    FrameAddressRegister # FAR
  ],
  ConfigFrame
]:
  slrNameFar_frame_dict: dict[tuple[str, FrameAddressRegister], ConfigFrame] = dict()

  for (idcode, far_dict) in bitstream.get_per_far_configuration_arrays().items():
    slrName = dev_summary.get_slr_name(idcode)
    for (far, config_frames) in far_dict.items():
      assert len(config_frames) == 1, f"Error: Found multiple writes to FAR 0x{far.to_hex()}!"
      frame = config_frames[0]
      slrNameFar_frame_dict[(slrName, far)] = frame

  return slrNameFar_frame_dict

def print_lut_info(
  bitlocator: BitLocator,
  lut: str,
  slrNameFar_frame_dict: dict[tuple[str, FrameAddressRegister], ConfigFrame]
) -> None:
  (slr_name, frame_addrs, frame_ofsts) = bitlocator.locate_lut(lut)
  print(f"{lut}")
  for (init_idx, (frame_addr, frame_ofst)) in enumerate(zip(frame_addrs, frame_ofsts)):
    config_frame = slrNameFar_frame_dict[(slr_name, frame_addr)]
    print(f"INIT[{init_idx:>2d}] -> {slr_name}, frame address: 0x{frame_addr.to_hex()} ({frame_addr}), frame offset: {frame_ofst:>4d}, frame byte offset in bitstream: {config_frame.byte_ofst}")

def print_ff_info(
  bitlocator: BitLocator,
  ff: str,
  slrNameFar_frame_dict: dict[tuple[str, FrameAddressRegister], ConfigFrame]
) -> None:
  (slr_name, frame_addr, frame_ofst) = bitlocator.locate_reg(ff)
  print(f"{ff}")
  config_frame = slrNameFar_frame_dict[(slr_name, frame_addr)]
  print(f"INIT -> {slr_name}, frame address: 0x{frame_addr.to_hex()} ({frame_addr}), frame offset: {frame_ofst:>4d}, frame byte offset in bitstream: {config_frame.byte_ofst}")

def print_bram_info(
  bitlocator: BitLocator,
  bram: str,
  slrNameFar_frame_dict: dict[tuple[str, FrameAddressRegister], ConfigFrame]
) -> None:
  (slr_name, content_frame_addrs, content_frame_ofsts, parity_frame_addrs, parity_frame_ofsts) = bitlocator.locate_bram(bram)
  print(f"{bram}")
  INIT = []
  print(f"GENERIC,INDEX,FILE_OFFSET,BIT_OFFSET")
  # python3 demo.py xczu4ev.bit --brams RAMB18_X2Y95
  for (init_idx, (frame_addr, frame_ofst)) in enumerate(zip(content_frame_addrs, content_frame_ofsts)):
    config_frame = slrNameFar_frame_dict[(slr_name, frame_addr)]
    #print(f"INIT[{init_idx:>5d}] -> {slr_name}, frame address: 0x{frame_addr.to_hex()} ({frame_addr}), frame offset: {frame_ofst:>4d}, frame byte offset in bitstream: {config_frame.byte_ofst}")
    word = int(frame_ofst / 32)
    bit_in_word = frame_ofst % 32
    array_i = int(init_idx / 256)
    bit_in_array = init_idx % 256
    print(f"INIT_{array_i:02X},{bit_in_array},{config_frame.byte_ofst},{frame_ofst}")
    if len(INIT) <= array_i:
      INIT.insert(array_i, [])
    INIT[array_i].insert(bit_in_array, f"{(config_frame.words[word] >> bit_in_word) & 1}")
    #print(f"INIT_{int(init_idx/256):02X}({init_idx%256}) = {(config_frame.words[word] >> bit_in_word) & 1}")
    #print(f"{init_idx},{word},{bit_in_word},{config_frame.words[word]:08x},{(config_frame.words[word] >> bit_in_word) & 1}")
  INITP = []
  for (init_idx, (frame_addr, frame_ofst)) in enumerate(zip(parity_frame_addrs, parity_frame_ofsts)):
    config_frame = slrNameFar_frame_dict[(slr_name, frame_addr)]
    #print(f"INIT_P[{init_idx:>5d}] -> {slr_name}, frame address: 0x{frame_addr.to_hex()} ({frame_addr}), frame offset: {frame_ofst:>4d}, frame byte offset in bitstream: {config_frame.byte_ofst}")
    word = int(frame_ofst / 32)
    bit_in_word = frame_ofst % 32
    array_i = int(init_idx / 256)
    bit_in_array = init_idx % 256
    print(f"INITP_{array_i:02X},{bit_in_array},{config_frame.byte_ofst},{frame_ofst}")
    if len(INITP) <= array_i:
      INITP.insert(array_i, [])
    INITP[array_i].insert(bit_in_array, f"{(config_frame.words[word] >> bit_in_word) & 1}")
    #print(f"INITP_{int(init_idx/256):02X},({init_idx%256}) = {(config_frame.words[word] >> bit_in_word) & 1}")
  for (i, bits) in enumerate(INIT):
    print(f"INIT_{i:02X} => \"{''.join(bits[::-1])}\",")
  for (i, bits) in enumerate(INITP):
    print(f"INITP_{i:02X} => \"{''.join(bits[::-1])}\",")


# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Demo application that locates a resource and prints its SLR name, frame addresses, and frame offsets. Each frame's position in the bitstream is also printed.")
  parser.add_argument("bitstream", type=str, help="Input bitstream (with header). Must be a full bitstream, not a partial one.")
  parser.add_argument("--luts", type=str, nargs="*", default=[], help="Name of LUTs to locate in the form of SLICE_X(\d+)Y(\d+)/[A-H]6LUT")
  parser.add_argument("--ffs", type=str, nargs="*", default=[], help="Name of Flip-Flops to locate in the form of SLICE_X(\d+)Y(\d+)/[A-H]FF2?")
  parser.add_argument("--brams", type=str, nargs="*", default=[], help="Name of 18K BRAMs to locate in the form of RAMB18_X(\d+)Y(\d+)")
  args = parser.parse_args()

  bitstream = Bitstream.from_file_path(Path(args.bitstream))
  assert not bitstream.is_partial(), f"Error: {bitstream} is a partial bitstream!"

  bitlocator = BitLocator(bitstream.header.fpga_part)
  dev_summary = resources.get_device_summary(bitstream.header.fpga_part)

  slrNameFar_frame_dict = extract_frames(bitstream, dev_summary)

  for lut in args.luts:
    print_lut_info(bitlocator, lut, slrNameFar_frame_dict)
    print()

  for ff in args.ffs:
    print_ff_info(bitlocator, ff, slrNameFar_frame_dict)
    print()

  for bram in args.brams:
    print_bram_info(bitlocator, bram, slrNameFar_frame_dict)
    print()