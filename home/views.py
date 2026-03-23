import datetime
import logging
import os
import pickle
import random
import threading
from types import SimpleNamespace
from urllib.parse import urlencode
import smtplib

import matplotlib
import pandas as pd
import seaborn as sns
import numpy as np
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.http import HttpResponseForbidden
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from .forms import UserProfileForm
from .models import VoiceConversationSession, userProfile
from .services.conversation_ai_service import ConversationAIService
from .services.speech_recognition_service import SpeechRecognitionService
from crop_predication_chatbot.security import (
    get_client_ip,
    is_password_hash,
    issue_user_token,
    rate_limit,
    require_auth,
    security_logger,
)

matplotlib.use('Agg')
import matplotlib.pyplot as plt


MODEL_TRAINING_STATE = {
    'is_training': False,
    'last_accuracy': None,
    'last_trained_at': None,
    'last_error': None,
}

logger = logging.getLogger(__name__)
api_logger = logging.getLogger('api_security')


def basefunction(request):
    return render(request, 'base.html')


def index(request):
    return render(request, 'index.html')


def userlogin(request):
    return render(request, 'userlogin.html')


def _get_logged_in_user(request):
    return getattr(request, 'auth_user', None) or userProfile.objects.filter(
        email=request.session.get('email', '')
    ).first()


def _require_logged_in_user(request):
    user = _get_logged_in_user(request)
    if user:
        return user
    messages.error(request, "You need to log in first.")
    return None


def _persist_temp_profile_photo(profile_photo):
    temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    extension = os.path.splitext(profile_photo.name)[1].lower()
    temp_file_path = os.path.join(temp_dir, f'{random.getrandbits(64):x}{extension}')
    with open(temp_file_path, 'wb+') as destination:
        for chunk in profile_photo.chunks():
            destination.write(chunk)
    return temp_file_path


def _smtp_configuration_error():
    if settings.EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend':
        return None
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        return (
            "SMTP is not configured yet. Add EMAIL_HOST_USER and EMAIL_HOST_PASSWORD "
            "or SMTP_USERNAME and SMTP_PASSWORD in .env."
        )
    return None


def _send_html_email(subject, html_message, recipients):
    config_error = _smtp_configuration_error()
    if config_error:
        raise RuntimeError(config_error)

    send_mail(
        subject,
        '',
        settings.DEFAULT_FROM_EMAIL,
        recipients,
        fail_silently=False,
        html_message=html_message,
    )


def _friendly_email_error(exc):
    config_error = _smtp_configuration_error()
    if config_error:
        return config_error
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "SMTP authentication failed. Check the Gmail app password in .env."
    if isinstance(exc, (smtplib.SMTPConnectError, TimeoutError)):
        return "SMTP server connection failed. Check EMAIL_HOST, EMAIL_PORT, and your internet connection."
    return f"OTP email could not be sent: {exc}"


def _dataset_paths():
    base_path = os.path.join(settings.MEDIA_ROOT, 'Crop_recommendation.csv')
    augmented_path = os.path.join(settings.MEDIA_ROOT, 'Crop_recommendation_augmented.csv')
    return base_path, augmented_path


def _load_training_dataframe(prefer_augmented=False):
    base_path, augmented_path = _dataset_paths()
    if prefer_augmented and os.path.exists(augmented_path):
        return pd.read_csv(augmented_path), augmented_path, 'augmented'
    if os.path.exists(base_path):
        return pd.read_csv(base_path), base_path, 'base'
    raise FileNotFoundError("Dataset file is missing.")


def _generate_synthetic_crop_data(df, synthetic_count):
    if synthetic_count <= 0 or df.empty:
        return df.iloc[0:0].copy()

    numeric_columns = ['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']
    synthetic_rows = []
    label_groups = {label: group.reset_index(drop=True) for label, group in df.groupby('label')}
    label_weights = df['label'].value_counts(normalize=True).to_dict()
    labels = list(label_groups.keys())
    probabilities = [label_weights[label] for label in labels]

    for _ in range(synthetic_count):
        label = np.random.choice(labels, p=probabilities)
        source_group = label_groups[label]
        sampled_row = source_group.sample(n=1, replace=True).iloc[0].copy()

        for column in numeric_columns:
            column_values = source_group[column]
            std = float(column_values.std()) if len(column_values) > 1 else 0.0
            noise_scale = std * 0.08
            if noise_scale:
                sampled_row[column] = float(sampled_row[column]) + np.random.normal(0, noise_scale)
            sampled_row[column] = float(np.clip(sampled_row[column], df[column].min(), df[column].max()))

        synthetic_rows.append(sampled_row)

    synthetic_df = pd.DataFrame(synthetic_rows, columns=df.columns)
    return synthetic_df


def _train_model_pipeline(synthetic_count=0, prefer_augmented=False):
    output_dir = os.path.join(settings.MEDIA_ROOT, 'eda')
    os.makedirs(output_dir, exist_ok=True)

    base_df, _, _ = _load_training_dataframe(prefer_augmented=prefer_augmented)
    base_df = base_df.dropna().drop_duplicates().reset_index(drop=True)

    synthetic_df = _generate_synthetic_crop_data(base_df, synthetic_count)
    training_df = pd.concat([base_df, synthetic_df], ignore_index=True)

    _, augmented_path = _dataset_paths()
    training_df.to_csv(augmented_path, index=False)

    sns.set_theme(style="whitegrid", context="talk", palette="Set2")

    for col in training_df.columns[:-1]:
        plt.figure(figsize=(8, 5))
        sns.histplot(
            training_df[col],
            kde=True,
            bins=30,
            color='#2ca02c',
            edgecolor='black',
            linewidth=0.7,
            alpha=0.9,
        )
        plt.title(f'{col} Distribution', fontsize=18, fontweight='bold', pad=15)
        plt.xlabel(col, fontsize=14)
        plt.ylabel('Count', fontsize=14)
        plt.grid(True, linestyle='--', linewidth=0.6, alpha=0.7)
        sns.despine()
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, f'{col}_distribution.png'), dpi=300)
        plt.close()

    plt.figure(figsize=(12, 10))
    corr = training_df.drop(columns=['label']).corr()
    sns.heatmap(
        corr,
        annot=True,
        fmt='.2f',
        cmap='coolwarm',
        linewidths=0.5,
        linecolor='white',
        cbar_kws={'shrink': 0.8, 'aspect': 30},
        square=True,
        annot_kws={"size": 10},
    )
    plt.title('Feature Correlation Matrix', fontsize=22, fontweight='bold', pad=20)
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'correlation_heatmap.png'), dpi=300)
    plt.close()

    X = training_df[['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']]
    y = training_df['label']
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    model_path = os.path.join(settings.MEDIA_ROOT, 'crop_model.pkl')
    with open(model_path, 'wb') as file_obj:
        pickle.dump(model, file_obj)

    MODEL_TRAINING_STATE['last_accuracy'] = round(accuracy * 100, 2)
    MODEL_TRAINING_STATE['last_trained_at'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    MODEL_TRAINING_STATE['last_error'] = None

    return {
        'accuracy': accuracy * 100,
        'base_count': len(base_df),
        'synthetic_count': len(synthetic_df),
        'training_count': len(training_df),
        'dataset_source': 'augmented' if len(synthetic_df) else 'base',
        'plots': [f'eda/{col}_distribution.png' for col in training_df.columns[:-1]] + ['eda/correlation_heatmap.png'],
    }


def _background_training_worker(synthetic_count=0, prefer_augmented=True):
    try:
        _train_model_pipeline(synthetic_count=synthetic_count, prefer_augmented=prefer_augmented)
    except Exception as exc:
        MODEL_TRAINING_STATE['last_error'] = str(exc)
    finally:
        MODEL_TRAINING_STATE['is_training'] = False


def _start_background_training(synthetic_count=0, prefer_augmented=True):
    if MODEL_TRAINING_STATE['is_training']:
        return False

    MODEL_TRAINING_STATE['is_training'] = True
    MODEL_TRAINING_STATE['last_error'] = None
    thread = threading.Thread(
        target=_background_training_worker,
        kwargs={'synthetic_count': synthetic_count, 'prefer_augmented': prefer_augmented},
        daemon=True,
    )
    thread.start()
    return True


def _model_path():
    return os.path.join(settings.MEDIA_ROOT, 'crop_model.pkl')


def _model_exists():
    return os.path.exists(_model_path())


def _get_or_create_voice_session_for_user(user, requested_session_id=None):
    session = None
    if requested_session_id:
        session = VoiceConversationSession.objects.filter(session_id=requested_session_id, user=user).first()

    if not session:
        session = VoiceConversationSession.objects.create(
            user=user,
            language='te-IN',
            channel='voice',
            title='Realtime Crop Voice Assistant',
            metadata={'transport': 'http-or-websocket'},
        )
    return session


def _predict_with_model(payload):
    with open(_model_path(), 'rb') as file_obj:
        model = pickle.load(file_obj)

    input_data = pd.DataFrame([payload])
    prediction = model.predict(input_data)[0]
    class_probabilities = {}
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(input_data)[0]
        class_labels = model.classes_
        class_probabilities = {
            label: round(prob * 100, 2)
            for label, prob in zip(class_labels, probs)
        }
    return prediction, class_probabilities


def userregister(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES)
        if form.is_valid():
            otp = random.randint(100000, 999999)
            email = form.cleaned_data['email']
            name = form.cleaned_data['name']
            otp_expiry_minutes = 5

            profile_photo = request.FILES.get('profile_photo')
            if profile_photo:
                request.session['profile_photo_path'] = _persist_temp_profile_photo(profile_photo)

            request.session['registration_data'] = dict(form.cleaned_data)
            request.session['registration_data']['profile_photo'] = None
            request.session['otp'] = otp
            request.session['otp_expiry'] = (
                datetime.datetime.now() + datetime.timedelta(minutes=otp_expiry_minutes)
            ).strftime("%Y-%m-%d %H:%M:%S")
            request.session['otp_sent_time'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            request.session['email'] = email

            subject = "OTP Verification - Secure Your Registration"
            message = format_html(
                """
                <p>Dear <b>{}</b>,</p>
                <p>Thank you for registering. To complete your registration, please use the following One-Time Password (OTP):</p>
                <h2 style="color: red; text-align: center;">{}</h2>
                <p>This OTP is valid for <b>{} minutes</b>. Do not share this OTP with anyone for security reasons.</p>
                <p>If you did not request this, please ignore this email.</p>
                <br>
                <p>Best Regards,</p>
                <p><b>System Generated Mail - No Reply Allowed</b></p>
                """,
                name,
                otp,
                otp_expiry_minutes,
            )

            try:
                _send_html_email(subject, message, [email])
            except Exception as exc:
                messages.error(request, _friendly_email_error(exc))
                return render(request, 'registration.html', {'form': form})

            messages.success(request, "OTP has been sent to your email. Please verify.")
            return redirect(reverse('verify_otp'))

        messages.error(request, "OOPS! Please correct the errors below.")
    else:
        form = UserProfileForm()

    return render(request, 'registration.html', {'form': form})


def verify_otp(request):
    email = None
    masked_email = None
    if 'registration_data' in request.session:
        email = request.session['registration_data'].get('email', '')
    if email:
        masked_email = f"{email[:3]}xxxxxxxx@{email.split('@')[-1]}"

    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        stored_otp = request.session.get('otp')
        otp_expiry = request.session.get('otp_expiry')

        if not stored_otp or not otp_expiry:
            messages.error(request, "OTP session expired. Please register again.")
            return redirect(reverse('userregister'))

        expiry_time = datetime.datetime.strptime(otp_expiry, "%Y-%m-%d %H:%M:%S")
        if datetime.datetime.now() > expiry_time:
            messages.error(request, "OTP has expired. Please request a new one.")
            return redirect(reverse('verify_otp'))

        if str(entered_otp) == str(stored_otp):
            registration_data = request.session.get('registration_data')
            profile_photo_path = request.session.get('profile_photo_path')

            if not registration_data:
                messages.error(request, "Session expired! Please register again.")
                return redirect(reverse('userregister'))

            user = userProfile(
                name=registration_data['name'],
                email=registration_data['email'],
                mobile=registration_data['mobile'],
            )
            user.set_password(registration_data['password'])

            if profile_photo_path and os.path.exists(profile_photo_path):
                with open(profile_photo_path, 'rb') as file_obj:
                    user.profile_photo.save(
                        os.path.basename(profile_photo_path),
                        ContentFile(file_obj.read()),
                        save=False,
                    )

            user.save()

            request.session.pop('registration_data', None)
            request.session.pop('profile_photo_path', None)
            request.session.pop('otp', None)
            request.session.pop('otp_expiry', None)
            request.session.pop('otp_sent_time', None)

            if profile_photo_path and os.path.exists(profile_photo_path):
                os.remove(profile_photo_path)

            messages.success(request, "Account created successfully! Wait for admin approval.")
            return redirect(reverse('userregister'))

        messages.error(request, "Invalid OTP! Please try again.")

    return render(request, 'verify_otp.html', {'masked_email': masked_email})


def resend_otp(request):
    email = request.session.get('email', '')
    name = request.session.get('registration_data', {}).get('name', '')
    if not email:
        messages.error(request, "Session expired! Please register again.")
        return redirect(reverse('userregister'))

    last_otp_time = request.session.get('otp_sent_time')
    current_time = datetime.datetime.now()
    if last_otp_time:
        last_otp_time = datetime.datetime.strptime(last_otp_time, "%Y-%m-%d %H:%M:%S")
        time_diff = (current_time - last_otp_time).seconds
        if time_diff < 60:
            messages.error(request, "Please wait 1 minute before resending OTP.")
            return redirect(reverse('verify_otp'))

    otp = random.randint(100000, 999999)
    request.session['otp'] = otp
    request.session['otp_sent_time'] = current_time.strftime("%Y-%m-%d %H:%M:%S")
    request.session['otp_expiry'] = (
        current_time + datetime.timedelta(minutes=5)
    ).strftime("%Y-%m-%d %H:%M:%S")

    try:
        send_otp_email(name, email, otp, 5)
    except Exception as exc:
        messages.error(request, _friendly_email_error(exc))
        return redirect(reverse('verify_otp'))

    messages.success(request, "A new OTP has been sent to your email.")
    return redirect(reverse('verify_otp'))


def send_otp_email(name, email, otp, expiry_minutes):
    subject = "OTP Verification - Secure Your Registration"
    message = format_html(
        """
        <p>Dear <b>{}</b>,</p>
        <p>Thank you for registering. Please use the following One-Time Password (OTP) to complete your registration:</p>
        <h2 style="color: red; text-align: center;">{}</h2>
        <p>This OTP is valid for <b>{} minutes</b>. Do not share this OTP with anyone for security reasons.</p>
        <p>If you did not request this, please ignore this email.</p>
        <br>
        <p>Best Regards,</p>
        <p><b>System Generated Mail - No Reply Allowed</b></p>
        """,
        name,
        otp,
        expiry_minutes,
    )
    _send_html_email(subject, message, [email])


def userlogincheck(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password')
        wants_json = request.headers.get('Accept', '').lower().find('application/json') >= 0

        if not email or not password:
            security_logger.info('Failed login attempt: missing fields email=%s ip=%s', email, get_client_ip(request))
            if wants_json:
                return JsonResponse({'error': 'Email and password are required.'}, status=400)
            messages.error(request, 'Email and password are required.')
            return render(request, 'userlogin.html')

        try:
            user = userProfile.objects.get(email__iexact=email)
            if user.status.lower() == 'blocked':
                security_logger.warning('Blocked user login denied email=%s ip=%s', email, get_client_ip(request))
                if wants_json:
                    return JsonResponse({'error': 'Your account is blocked.'}, status=403)
                messages.error(request, 'Your account is blocked. Please contact our admin team.')
                return render(request, 'userlogin.html')
            if user.status.lower() != 'activated':
                security_logger.info('Inactive user login denied email=%s ip=%s', email, get_client_ip(request))
                if wants_json:
                    return JsonResponse({'error': 'Your account is not active yet.'}, status=403)
                messages.warning(request, 'Your account is not active. Please wait for admin approval.')
                return render(request, 'userlogin.html')
            authenticated = False
            if is_password_hash(user.password):
                authenticated = check_password(password, user.password)
            else:
                authenticated = user.password == password
                if authenticated:
                    user.password = make_password(password)
                    user.confirm_password = ''
                    user.save(update_fields=['password', 'confirm_password'])

            if authenticated:
                request.session.flush()
                request.session['email'] = user.email
                request.session['name'] = user.name
                request.session['profile_photo'] = (
                    user.profile_photo.url if user.profile_photo else f"{settings.MEDIA_URL}profile_photos/default.gif"
                )
                request.session['user_role'] = 'user'
                request.session.cycle_key()
                if wants_json:
                    return JsonResponse({
                        'token': issue_user_token(user),
                        'expires_in': settings.JWT_ACCESS_TTL_SECONDS,
                        'user': {'email': user.email, 'name': user.name, 'role': 'user'},
                    })
                return redirect('userhome', name=user.name)

            security_logger.warning('Failed login attempt: invalid password email=%s ip=%s', email, get_client_ip(request))
            if wants_json:
                return JsonResponse({'error': 'Invalid credentials.'}, status=401)
            messages.error(request, 'Invalid password. Please try again.')
            return render(request, 'userlogin.html')
        except userProfile.DoesNotExist:
            security_logger.warning('Failed login attempt: unknown email=%s ip=%s', email, get_client_ip(request))
            if wants_json:
                return JsonResponse({'error': 'Invalid credentials.'}, status=401)
            messages.error(request, 'Email is not registered. Please sign up first.')
            return render(request, 'userlogin.html')

    return render(request, 'userlogin.html')


@require_POST
def api_token_obtain_view(request):
    request.META['HTTP_ACCEPT'] = 'application/json'
    return userlogincheck(request)


@require_auth(roles=('user',))
def userhome(request, name):
    user = _get_logged_in_user(request)
    if not _model_exists():
        _start_background_training(prefer_augmented=True)
    return render(request, 'users/userhome.html', {'user': user, 'name': name})


@require_auth(roles=('admin',))
def train_model_view(request):
    user = _get_logged_in_user(request)
    display_user = user or SimpleNamespace(name=request.session.get('admin_username', 'admin'))

    output_dir = os.path.join(settings.MEDIA_ROOT, 'eda')
    os.makedirs(output_dir, exist_ok=True)

    synthetic_count = 0
    if request.method == 'POST':
        try:
            synthetic_count = max(0, int(request.POST.get('synthetic_count', 0)))
        except (TypeError, ValueError):
            messages.error(request, "Synthetic row count must be a valid number.")
            return redirect('train_model_view')

    try:
        training_result = _train_model_pipeline(synthetic_count=synthetic_count, prefer_augmented=False)
    except FileNotFoundError:
        messages.error(request, "Dataset file is missing.")
        return redirect('AdminHome')

    return render(request, 'users/results.html', {
        'media_url': settings.MEDIA_URL,
        'user': display_user,
        'name': display_user.name,
        **training_result,
    })


@require_auth(roles=('user',))
def predict_crop_view(request):
    user = _get_logged_in_user(request)

    if not _model_exists():
        _start_background_training(prefer_augmented=True)

    return render(request, 'users/predict_crop.html', {
        'user': user,
        'name': user.name,
        'media_url': settings.MEDIA_URL,
        'model_ready': _model_exists(),
        'training_status': MODEL_TRAINING_STATE,
    })


@require_auth(api=True, roles=('user', 'admin'))
def model_status_view(request):
    if not _model_exists() and not MODEL_TRAINING_STATE['is_training']:
        _start_background_training(prefer_augmented=True)

    return JsonResponse({
        'ready': _model_exists(),
        'is_training': MODEL_TRAINING_STATE['is_training'],
        'last_accuracy': MODEL_TRAINING_STATE['last_accuracy'],
        'last_trained_at': MODEL_TRAINING_STATE['last_trained_at'],
        'last_error': MODEL_TRAINING_STATE['last_error'],
    })


@require_auth(api=True, roles=('user', 'admin'))
def predict_crop_api(request):
    required_fields = ['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']
    try:
        payload = {field: float(request.GET.get(field, '')) for field in required_fields}
    except ValueError:
        return JsonResponse({'error': 'All parameters must be valid numbers.'}, status=400)

    if not _model_exists():
        _start_background_training(prefer_augmented=True)
        return JsonResponse({
            'error': 'Model is training in the background.',
            'ready': False,
            'is_training': True,
        }, status=202)

    try:
        prediction, class_probabilities = _predict_with_model(payload)
    except Exception as exc:
        return JsonResponse({'error': str(exc), 'ready': False}, status=500)

    return JsonResponse({
        'ready': True,
        'prediction': str(prediction),
        'class_probabilities': class_probabilities,
        'inputs': payload,
    })

@require_auth(roles=('user',))
def chatfunction(request):
    user = _get_logged_in_user(request)

    requested_session_id = request.GET.get('session_id')
    session = _get_or_create_voice_session_for_user(user, requested_session_id)

    websocket_url = f"/ws/voice-assistant/?{urlencode({'session_id': str(session.session_id), 'token': issue_user_token(user)})}"
    recent_turns = list(session.turns.order_by('created_at').values(
        'role', 'message_text', 'predicted_crop', 'created_at', 'extracted_parameters'
    ))
    conversation_service = ConversationAIService()
    speech_service = SpeechRecognitionService()

    return render(request, "users/chat.html", {
        'user': user,
        'name': user.name,
        'voice_session_id': str(session.session_id),
        'websocket_url': websocket_url,
        'voice_text_api_url': reverse('voice_text_chat_api'),
        'voice_audio_api_url': reverse('voice_audio_chat_api'),
        'provider_status': {
            'asr_configured': speech_service.is_configured(),
            'tts_configured': conversation_service.tts_service.is_configured(),
            'ai_configured': conversation_service.is_configured(),
        },
        'recent_turns': recent_turns,
    })


@require_POST
@require_auth(api=True, roles=('user',))
@rate_limit(
    key_prefix='voice-text',
    limit=settings.VOICE_TEXT_RATE_LIMIT,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
)
def voice_text_chat_api(request):
    user = _get_logged_in_user(request)

    session = _get_or_create_voice_session_for_user(user, request.POST.get('session_id'))
    text = request.POST.get('text', '').strip()
    if not text:
        return JsonResponse({'error': 'Text is required.'}, status=400)

    turn = ConversationAIService().process_user_text(
        session,
        text,
        source='text',
        language='te-IN',
        asr_confidence=None,
        model_metadata={'transport': 'http'},
    )
    return JsonResponse({
        'type': 'assistant.turn',
        'transcript': turn.transcript,
        'normalized_text': turn.normalized_text,
        'intent': turn.intent,
        'parameters': turn.parameters,
        'missing_parameters': turn.missing_parameters,
        'prediction': turn.prediction,
        'class_probabilities': turn.class_probabilities,
        'assistant_text': turn.assistant_text,
        'audio_url': turn.audio_url,
        'asr_confidence': turn.asr_confidence,
        'low_confidence': turn.low_confidence,
        'fallback_to_text': turn.fallback_to_text,
        'model_metadata': turn.model_metadata,
    })


@require_POST
@require_auth(api=True, roles=('user',))
@rate_limit(
    key_prefix='voice-audio',
    limit=settings.VOICE_AUDIO_RATE_LIMIT,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
)
def voice_audio_chat_api(request):
    user = _get_logged_in_user(request)

    session = _get_or_create_voice_session_for_user(user, request.POST.get('session_id'))
    audio_file = request.FILES.get('audio')
    if not audio_file:
        return JsonResponse({'error': 'Audio file is required.'}, status=400)

    speech_service = SpeechRecognitionService()
    asr_result = speech_service.transcribe_audio(
        audio_file.read(),
        'te-IN',
        mime_type=getattr(audio_file, 'content_type', '') or 'audio/webm',
        filename=getattr(audio_file, 'name', 'voice.webm'),
    )
    api_logger.warning(
        'voice_audio_chat_api asr provider=%s transcript_present=%s confidence=%s raw=%s',
        asr_result.provider,
        bool(asr_result.transcript),
        asr_result.confidence,
        asr_result.raw,
    )
    conversation_service = ConversationAIService()

    if asr_result.confidence < speech_service.confidence_threshold or not asr_result.transcript:
        turn = conversation_service.build_low_confidence_reply(
            session,
            "Low-confidence ASR fallback triggered.",
            asr_result.confidence,
            {'asr_provider': asr_result.provider, 'asr_raw': asr_result.raw, 'transport': 'http'},
        )
    else:
        turn = conversation_service.process_user_text(
            session,
            asr_result.transcript,
            source='voice',
            language='te-IN',
            asr_confidence=asr_result.confidence,
            model_metadata={'asr_provider': asr_result.provider, 'asr_raw': asr_result.raw, 'transport': 'http'},
        )

    return JsonResponse({
        'type': 'assistant.turn',
        'transcript': turn.transcript,
        'normalized_text': turn.normalized_text,
        'intent': turn.intent,
        'parameters': turn.parameters,
        'missing_parameters': turn.missing_parameters,
        'prediction': turn.prediction,
        'class_probabilities': turn.class_probabilities,
        'assistant_text': turn.assistant_text,
        'audio_url': turn.audio_url,
        'asr_confidence': turn.asr_confidence,
        'low_confidence': turn.low_confidence,
        'fallback_to_text': turn.fallback_to_text,
        'model_metadata': turn.model_metadata,
    })


@require_auth(roles=('user',))
def dataset_view(request):
    user = _get_logged_in_user(request)

    try:
        dataset, _, dataset_source = _load_training_dataframe(prefer_augmented=True)
    except FileNotFoundError:
        messages.error(request, "Dataset file is missing.")
        return redirect('userhome', name=user.name)

    dataset = dataset.iloc[:, :-1]
    dataset_dict = dataset.to_dict(orient='records')

    return render(request, 'users/datasetview.html', {
        'dataset': dataset_dict,
        'user': user,
        'name': user.name,
        'dataset_source': dataset_source,
    })
