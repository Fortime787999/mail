from django.contrib.auth.decorators import login_required


class LoginRequiredMixin(object):
    @classmethod
    def as_view(cls,**initkwargs):
        view = super().as_view()
        view = login_required(view)
        return view
