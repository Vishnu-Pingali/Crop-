from django.contrib import admin
from .models import userProfile

# Register your models here.

@admin.register(userProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'mobile', 'profile_photo')
    search_fields = ('name', 'email', 'mobile')

