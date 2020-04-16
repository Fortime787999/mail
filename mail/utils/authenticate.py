from django.contrib.auth.backends import ModelBackend
from users.models import User
class MailModelBacked(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(username=username)
        except Exception as e:
            try:
                user = User.objects.get(mobile=username)
            except Exception as e:
                return None
        if user.check_password(password):
            return user
        else:
            return None
