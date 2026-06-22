from django.contrib import admin

from .models import Asleb


@admin.register(Asleb)
class AslebAdmin(admin.ModelAdmin):
    list_display = ('nama', 'nim', 'no_hp', 'program_studi', 'semester', 'status')
    list_filter = ('status', 'program_studi', 'semester')
    search_fields = ('nama', 'nim', 'no_hp', 'email', 'program_studi')
