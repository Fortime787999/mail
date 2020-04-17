from itsdangerous.jws import TimedJSONWebSignatureSerializer
from django.conf import settings


def dumps(Dict,expires):
    s = TimedJSONWebSignatureSerializer(settings.SECRET_KEY, expires_in =expires)
    json_str = s.dumps(Dict).decode()
    return json_str


def loads(Str, expires):
    s = TimedJSONWebSignatureSerializer(settings.SECRET_KEY, expires_in=expires)
    try:
        Dict = s.loads(Str)
    except Exception as e:
        return None
    else:
        return Dict
