"""
URL configuration for recommend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from home import views
from admins import views as vi
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('',views.basefunction,name='basefunction'),
    

    path('userlogin/',views.userlogin,name='userlogin'),

    path('userregister/',views.userregister,name='userregister'),
    path('verify_otp/',views.verify_otp, name='verify_otp'),
    path('resend_otp/',views.resend_otp, name='resend_otp'),
    path('userlogincheck/',views.userlogincheck,name='userlogincheck'),
    path('api/auth/token/', views.api_token_obtain_view, name='api_token_obtain_view'),
    path('userhome/<str:name>/', views.userhome, name='userhome'),
    
    

    path('train_model_view/', views.train_model_view, name='train_model_view'),
    path('predict_crop_view/', views.predict_crop_view, name='predict_crop_view'),
    path('api/model-status/', views.model_status_view, name='model_status_view'),
    path('api/predict-crop/', views.predict_crop_api, name='predict_crop_api'),
    path('dataset_view/', views.dataset_view, name='dataset_view'),
    path('api/voice/text/', views.voice_text_chat_api, name='voice_text_chat_api'),
    path('api/voice/audio/', views.voice_audio_chat_api, name='voice_audio_chat_api'),



    

    
    path('chatfunction/',views.chatfunction,name='chatfunction'),
    
    




    # ---------------------admin--------------

    path('adminlogin/',vi.adminlogin,name='adminlogin'),
    path('AdminLoginCheck/',vi.AdminLoginCheck,name='AdminLoginCheck'),
    path('api/admin/token/', vi.admin_token_obtain_view, name='admin_token_obtain_view'),
    path('adminlogout/',vi.adminlogout,name='adminlogout'),
    path('AdminHome/',vi.AdminHome,name='AdminHome'),
    path('RegisterUsersView/',vi.RegisterUsersView,name='RegisterUsersView'),
    path('activate_user/<int:id>/',vi.activate_user,name='activate_user'),
    path('BlockUser/<int:id>/',vi.BlockUser,name='BlockUser'),
    path('UnblockUser/<int:id>/',vi.UnblockUser,name='UnblockUser'),
    path('DeleteUser/<int:id>/',vi.DeleteUser,name='DeleteUser'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
