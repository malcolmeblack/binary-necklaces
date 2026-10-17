try:
    from src import calc, tessellate
except ModuleNotFoundError as exc:
    if exc.name != 'src':
        raise
    import calc, tessellate
import re
import base64
import json
import io


def encode(image):
	buffer = io.BytesIO()
	image.save(buffer, format='GIF')
	img_data = buffer.getvalue()
	img_base64 = base64.b64encode(img_data).decode('utf-8')
	return img_base64


def handler(event, context):

	query_params = event.get('queryStringParameters') or {}
	bs = query_params.get('bitstring', '')
	if not isinstance(bs, str) or re.fullmatch(r'[01]{1,64}', bs) is None:
		return {'statusCode': 400, 'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'}, 'body': json.dumps({'error': 'Enter a binary word of length 1 to 64.'})}
	
	bs = calc.cycle_root(bs)
	n = len(bs)
	s = 1.5
	repeats = int(25*s) // n + 1
	long_n = n * repeats
	long_bs = bs * repeats
	
	image = tessellate.create_image(long_bs, s)
	encoded_image = encode(image)

	response = {
		'statusCode': 200,
		'headers': {
			'Access-Control-Allow-Origin': '*',
			'Content-Type': 'image/gif'
		},
		'isBase64Encoded': True,
		'body': encoded_image
	}
	
	return response
