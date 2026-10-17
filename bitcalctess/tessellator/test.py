import calc, tessellate
import base64
import json
import io
from PIL import Image


def handler(bs):
	bs = calc.root(bs)
	n = len(bs)
	s = 1.5
	repeats = int(25*s) // n + 1
	long_n = n * repeats
	long_bs = bs * repeats

	im = tessellate.create_image(long_bs, s)
	im.save(f'{len(bs)}.png')


bss = [
	'0',
	'011',
	'0011101',
	'000111101011001',
	'000011111010100110001',
	'000001000011000101001111010001110010010110111011001101010111111'
]
for bs in bss:
	handler(bs)