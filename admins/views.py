from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from crop_predication_chatbot.security import get_client_ip, issue_admin_token, require_auth, security_logger
from home.models import userProfile


def adminlogin(request):
    return render(request, 'adminlogin.html', {})


def adminlogout(request):
    request.session.flush()
    return render(request, 'base.html')


def _admin_password_matches(raw_password: str) -> bool:
    if settings.ADMIN_PASSWORD_HASH:
        return check_password(raw_password, settings.ADMIN_PASSWORD_HASH)
    return settings.ADMIN_PASSWORD == raw_password


@require_POST
def AdminLoginCheck(request):
    username = request.POST.get('loginid', '').strip()
    password = request.POST.get('pswd', '')
    wants_json = 'application/json' in request.headers.get('Accept', '').lower()

    if username == settings.ADMIN_USERNAME and _admin_password_matches(password):
        request.session.flush()
        request.session['admin_authenticated'] = True
        request.session['admin_username'] = username
        request.session['user_role'] = 'admin'
        request.session.cycle_key()
        if wants_json:
            return JsonResponse({
                'token': issue_admin_token(username),
                'expires_in': settings.JWT_ACCESS_TTL_SECONDS,
                'user': {'username': username, 'role': 'admin'},
            })
        return redirect('AdminHome')

    security_logger.warning(
        'Failed admin login attempt username=%s ip=%s',
        username,
        get_client_ip(request),
    )
    if wants_json:
        return JsonResponse({'error': 'Invalid admin credentials.'}, status=401)
    messages.error(request, 'Please check your login details.')
    return render(request, 'adminlogin.html', {})


@require_POST
def admin_token_obtain_view(request):
    request.META['HTTP_ACCEPT'] = 'application/json'
    return AdminLoginCheck(request)


@require_auth(roles=('admin',), redirect_to='adminlogin')
def AdminHome(request):
    user_name = request.session.get('admin_username') or getattr(request, 'auth_context', {}).get('sub')
    return render(request, 'admins/AdminHome.html', {'user_name': user_name})


@require_auth(roles=('admin',), redirect_to='adminlogin')
def RegisterUsersView(request):
    search_query = request.GET.get('search', '').strip()

    if search_query:
        data = userProfile.objects.filter(
            Q(name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(mobile__icontains=search_query)
        ).order_by('-id')
    else:
        data = userProfile.objects.all().order_by('-id')

    paginator = Paginator(data, 11)
    page_number = request.GET.get('page')
    data_page = paginator.get_page(page_number)
    start_index = (data_page.number - 1) * paginator.per_page
    user_name = request.session.get('admin_username') or getattr(request, 'auth_context', {}).get('sub')

    return render(request, 'admins/viewregisterusers.html', {
        'data': data_page,
        'user_name': user_name,
        'start_index': start_index,
        'search_query': search_query,
    })


@require_auth(roles=('admin',), redirect_to='adminlogin')
def activate_user(request, id):
    updated = userProfile.objects.filter(id=id, status='waiting').update(status='activated')

    if updated:
        messages.success(request, f'User with ID {id} has been activated and can now log in.')
    else:
        messages.error(request, f'User with ID {id} is either not found or already activated.')
    return redirect('RegisterUsersView')


@require_auth(roles=('admin',), redirect_to='adminlogin')
def BlockUser(request, id):
    updated = userProfile.objects.filter(id=id, status='activated').update(status='blocked')

    if updated:
        messages.success(request, f'User with ID {id} has been blocked.')
    else:
        messages.error(request, f'User with ID {id} cannot be blocked or is not activated.')
    return redirect('RegisterUsersView')


@require_auth(roles=('admin',), redirect_to='adminlogin')
def UnblockUser(request, id):
    updated = userProfile.objects.filter(id=id, status='blocked').update(status='activated')

    if updated:
        messages.success(request, f'User with ID {id} has been unblocked.')
    else:
        messages.error(request, f'User with ID {id} cannot be unblocked or is not blocked.')
    return redirect('RegisterUsersView')


@require_auth(roles=('admin',), redirect_to='adminlogin')
def DeleteUser(request, id):
    user = get_object_or_404(userProfile, id=id)
    user.delete()
    messages.success(request, f'User with ID {id} has been deleted.')
    return redirect('RegisterUsersView')
