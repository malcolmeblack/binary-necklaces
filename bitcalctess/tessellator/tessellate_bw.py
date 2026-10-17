"""Periodic tessellations derived from a staggered space-time diagram.

The row update uses positions i and i+1 for the drawing coordinates. It is a
rotation of D(w), so it induces the same adjacent-XOR map on necklaces.
"""
from PIL import Image, ImageDraw

def create_image(long_bs):

	width, height = 2000, 2000
	image = Image.new('RGB', (width, height), color='#ffffff')
	draw = ImageDraw.Draw(image)

	global long_n
	long_n = len(long_bs)

	# lines
	row_word = long_bs
	shift = 0
	for y in range(52):
		long_ar = [int(i) for i in row_word]
		for x in range(long_n):

			# bit coordinates
			l0 = ((x + shift) % long_n, y)
			l2 = ((x + shift + 1) % long_n, y)
			u1 = ((x + shift + 0.5) % long_n, y + 1)
			u3 = ((x + shift + 1.5) % long_n, y + 1)
			# pixel coordinates
			L0 = transform(l0[0], l0[1])
			L2 = transform(l2[0], l2[1])
			U1 = transform(u1[0], u1[1])
			U3 = transform(u3[0], u3[1])

			if long_ar[x] == 0:
				if long_ar[(x + 1) % long_n] == 1:
					if long_ar[(x + 2) % long_n] == 0:
						# half-triangle visible on the left
						if u1[0] > l2[0] < u3[0]:
							U1 = (L2[0] - 20, U1[1])
						# half-triangle visible on the right
						if u1[0] < l2[0] > u3[0]:
							U3 = (L2[0] + 20, U3[1])
						# triangle
						draw.polygon((L2, U1, U3), fill='#000000')
						draw.line((L2, U1, U3, L2), fill='#000000', width=5)
					else:
						# wraparound
						if l2[0] < u1[0]:
							U1 = (L2[0] - 20, U1[1])
						# backward diagonal line
						draw.line((L2, U1), fill='#000000', width=5)
			else:
				if long_ar[(x + 1) % long_n] == 0:
					# wraparound
					if l0[0] > u1[0]:
						L0 = (U1[0] - 20, L0[1])
					# forward diagonal line
					draw.line((L0, U1), fill='#000000', width=5)
				else:
					# wraparound
					if l0[0] > l2[0]:
						L0 = (L2[0] - 40, L0[1])
					# horizontal line
					draw.line((L0, L2), fill='#000000', width=5)

		shift = shift + 0.5
		row_word = adjacent_xor_staggered(row_word)

	return image

	
def transform(x, y):
	x = 40 * x
	y = 2000 - 40 * y
	return (x, y)


def adjacent_xor_staggered(bs):
	# first bit shifts 0.5 bits to the right
	l = ''
	for i in range(len(bs)):
		l += str(int(bs[i]) ^ int(bs[(i +1) % len(bs)]))
	return l


	