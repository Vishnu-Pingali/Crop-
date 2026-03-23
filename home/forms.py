import os
import re
import uuid

from django import forms
from django.conf import settings
from PIL import Image

from .models import userProfile

class UserProfileForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': ' Enter Password'}),
        label="Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': ' Confirm Password'}),
        label="Confirm Password"
    )

    class Meta:
        model = userProfile
        fields = ['name', 'email', 'password', 'confirm_password', 'mobile', 'profile_photo']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': ' Email Address'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' Mobile Number'}),
            'profile_photo': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not re.match(r'^[A-Za-z\s]+$', name):
            raise forms.ValidationError("Name should contain only letters and spaces.")
        return name

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if userProfile.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def clean_mobile(self):
        mobile = self.cleaned_data.get('mobile')
        if not mobile.isdigit():
            raise forms.ValidationError("Mobile number must contain only digits.")
        if len(mobile) < 10 or len(mobile) > 15:
            raise forms.ValidationError("Mobile number must be between 10 and 15 digits.")
        if userProfile.objects.filter(mobile=mobile).exists():
            raise forms.ValidationError("This mobile number is already registered.")
        return mobile

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if len(password) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long.")
        if not any(char.isdigit() for char in password):
            raise forms.ValidationError("Password must contain at least one digit.")
        if not any(char.isalpha() for char in password):
            raise forms.ValidationError("Password must contain at least one letter.")
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data
    
    def clean_profile_photo(self):
        profile_photo = self.cleaned_data.get('profile_photo')
        if not profile_photo:
            return profile_photo

        extension = os.path.splitext(profile_photo.name)[1].lower()
        if extension not in settings.ALLOWED_PROFILE_IMAGE_EXTENSIONS:
            raise forms.ValidationError("Only JPG, JPEG, PNG, and GIF profile images are allowed.")

        if profile_photo.size > settings.MAX_PROFILE_UPLOAD_SIZE:
            raise forms.ValidationError("Profile image exceeds the allowed size limit.")

        try:
            image = Image.open(profile_photo)
            image.verify()
        except Exception as exc:
            raise forms.ValidationError("Uploaded file is not a valid image.") from exc
        finally:
            profile_photo.seek(0)

        profile_photo.name = f"{uuid.uuid4().hex}{extension}"
        return profile_photo
