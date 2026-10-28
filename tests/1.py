import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

private_key = ec.generate_private_key(ec.SECP256R1())
private_bytes = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)
private_b64 = base64.b64encode(private_bytes).decode('utf-8')

public_key = private_key.public_key()
public_bytes = public_key.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint
)
public_b64 = base64.urlsafe_b64encode(public_bytes).decode('utf-8').rstrip('=')

print('\n======== 复制下面的内容替换到 .env ========')
print(f'VAPID_PUBLIC_KEY={public_b64}')
print(f'VAPID_PRIVATE_KEY={private_b64}')
print('VAPID_SUBJECT=mailto:admin@xinshi.com')
print('==========================================\n')
