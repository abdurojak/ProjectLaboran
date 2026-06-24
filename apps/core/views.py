from django.shortcuts import redirect


class PostOnlyDeleteMixin:
    def get(self, request, *args, **kwargs):
        return redirect(self.get_success_url())
