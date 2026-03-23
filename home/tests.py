import os
import pickle
import shutil
import tempfile
from unittest.mock import patch

import pandas as pd
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from sklearn.ensemble import RandomForestClassifier

from .models import VoiceConversationSession, VoiceConversationTurn, userProfile
from .services.conversation_ai_service import ConversationAIService
from .services.language_processing_service import LanguageProcessingService
from .services.speech_recognition_service import ASRResult, SpeechRecognitionService
from .services.text_to_speech_service import TextToSpeechService
from crop_predication_chatbot.env import load_env_file


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RegistrationOtpTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_verify_otp_creates_user_from_session_data(self):
        session = self.client.session
        session['registration_data'] = {
            'name': 'Test User',
            'email': 'test@example.com',
            'password': 'Password1',
            'confirm_password': 'Password1',
            'mobile': '9876543210',
            'profile_photo': None,
        }
        session['otp'] = 123456
        session['otp_expiry'] = '2099-01-01 12:00:00'
        session.save()

        response = self.client.post(reverse('verify_otp'), {'otp': '123456'})

        self.assertRedirects(response, reverse('userregister'))
        user = userProfile.objects.get(email='test@example.com')
        self.assertTrue(check_password('Password1', user.password))
        self.assertEqual(user.confirm_password, '')

    def test_protected_user_page_redirects_without_session(self):
        response = self.client.get(reverse('predict_crop_view'))

        self.assertRedirects(response, reverse('userlogin'))

    def test_resend_otp_uses_configured_from_email(self):
        session = self.client.session
        session['email'] = 'otp@example.com'
        session['registration_data'] = {'name': 'OTP User'}
        session.save()

        response = self.client.get(reverse('resend_otp'))

        self.assertRedirects(response, reverse('verify_otp'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD='',
        DEFAULT_FROM_EMAIL='no-reply@localhost',
    )
    def test_registration_shows_clear_error_when_smtp_is_not_configured(self):
        response = self.client.post(reverse('userregister'), {
            'name': 'Mail User',
            'email': 'mail-user@example.com',
            'password': 'Password1',
            'confirm_password': 'Password1',
            'mobile': '9876543201',
        })

        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(any('SMTP is not configured yet' in str(message) for message in messages))


class SyntheticTrainingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.temp_media_root = tempfile.mkdtemp()
        self.user = userProfile.objects.create(
            name='Trainer',
            email='trainer@example.com',
            password='Password1',
            confirm_password='Password1',
            mobile='9988776655',
            status='activated',
        )

        dataset = pd.DataFrame([
            {'N': 90, 'P': 42, 'K': 43, 'temperature': 20.8, 'humidity': 82.0, 'ph': 6.5, 'rainfall': 202.9, 'label': 'rice'},
            {'N': 85, 'P': 58, 'K': 41, 'temperature': 21.7, 'humidity': 80.3, 'ph': 7.0, 'rainfall': 226.6, 'label': 'rice'},
            {'N': 22, 'P': 67, 'K': 18, 'temperature': 27.1, 'humidity': 55.2, 'ph': 6.2, 'rainfall': 88.4, 'label': 'mungbean'},
            {'N': 25, 'P': 70, 'K': 20, 'temperature': 28.0, 'humidity': 57.4, 'ph': 6.4, 'rainfall': 91.3, 'label': 'mungbean'},
        ])
        dataset.to_csv(os.path.join(self.temp_media_root, 'Crop_recommendation.csv'), index=False)

        session = self.client.session
        session['admin_authenticated'] = True
        session['admin_username'] = 'admin'
        session.save()

    def tearDown(self):
        shutil.rmtree(self.temp_media_root, ignore_errors=True)

    def test_train_model_view_generates_synthetic_rows(self):
        with self.settings(MEDIA_ROOT=self.temp_media_root):
            response = self.client.post(reverse('train_model_view'), {'synthetic_count': 5})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['synthetic_count'], 5)
        self.assertEqual(response.context['training_count'], 9)
        self.assertTrue(
            os.path.exists(os.path.join(self.temp_media_root, 'Crop_recommendation_augmented.csv'))
        )

    def test_predict_crop_api_returns_prediction_when_model_exists(self):
        training_frame = pd.read_csv(os.path.join(self.temp_media_root, 'Crop_recommendation.csv'))
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(
            training_frame[['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']],
            training_frame['label'],
        )
        with open(os.path.join(self.temp_media_root, 'crop_model.pkl'), 'wb') as file_obj:
            pickle.dump(model, file_obj)

        with self.settings(MEDIA_ROOT=self.temp_media_root):
            response = self.client.get(reverse('predict_crop_api'), {
                'N': 90,
                'P': 42,
                'K': 43,
                'temperature': 20.8,
                'humidity': 82.0,
                'ph': 6.5,
                'rainfall': 202.9,
            })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ready'])
        self.assertIn('prediction', response.json())


class VoiceAssistantServiceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.temp_media_root = tempfile.mkdtemp()
        self.user = userProfile.objects.create(
            name='Voice User',
            email='voice@example.com',
            password='Password1',
            confirm_password='Password1',
            mobile='9000000001',
            status='activated',
        )
        dataset = pd.DataFrame([
            {'N': 90, 'P': 42, 'K': 43, 'temperature': 20.8, 'humidity': 82.0, 'ph': 6.5, 'rainfall': 202.9, 'label': 'rice'},
            {'N': 91, 'P': 41, 'K': 42, 'temperature': 21.1, 'humidity': 81.2, 'ph': 6.6, 'rainfall': 203.2, 'label': 'rice'},
            {'N': 30, 'P': 10, 'K': 20, 'temperature': 28.0, 'humidity': 55.0, 'ph': 6.2, 'rainfall': 80.0, 'label': 'maize'},
            {'N': 29, 'P': 11, 'K': 21, 'temperature': 27.5, 'humidity': 56.0, 'ph': 6.1, 'rainfall': 82.0, 'label': 'maize'},
        ])
        dataset.to_csv(os.path.join(self.temp_media_root, 'Crop_recommendation.csv'), index=False)
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(
            dataset[['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']],
            dataset['label'],
        )
        with open(os.path.join(self.temp_media_root, 'crop_model.pkl'), 'wb') as file_obj:
            pickle.dump(model, file_obj)

    def tearDown(self):
        shutil.rmtree(self.temp_media_root, ignore_errors=True)

    def _login_voice_user(self):
        session = self.client.session
        session['email'] = self.user.email
        session['name'] = self.user.name
        session.save()

    def _auth_headers(self):
        return {'HTTP_ACCEPT': 'application/json'}

    def test_language_processing_extracts_telugu_style_parameter_values(self):
        service = LanguageProcessingService()

        analysis = service.analyze('నైట్రోజన్ 90 ఫాస్ఫరస్ 42 పొటాషియం 43 ఉష్ణోగ్రత 21 ఆర్ద్రత 82 పీహెచ్ 6.5 వర్షపాతం 203')

        self.assertEqual(analysis.intent, 'crop_prediction')
        self.assertEqual(analysis.parameters['N'], 90.0)
        self.assertEqual(analysis.parameters['rainfall'], 203.0)

    def test_conversation_ai_service_persists_turns_and_prediction(self):
        session = VoiceConversationSession.objects.create(user=self.user, title='Test Voice Session')
        service = ConversationAIService()

        with self.settings(MEDIA_ROOT=self.temp_media_root):
            result = service.process_user_text(
                session,
                'N 90 P 42 K 43 temperature 20.8 humidity 82 ph 6.5 rainfall 202.9 crop recommend',
                source='text',
                language='te-IN',
                asr_confidence=0.88,
            )

        self.assertEqual(result.prediction, 'rice')
        self.assertEqual(VoiceConversationTurn.objects.filter(session=session).count(), 2)
        self.assertTrue(
            VoiceConversationTurn.objects.filter(session=session, role='assistant', predicted_crop='rice').exists()
        )

    def test_voice_text_chat_api_returns_prediction_payload(self):
        self._login_voice_user()
        session = VoiceConversationSession.objects.create(user=self.user, title='HTTP Chat Session')

        with self.settings(MEDIA_ROOT=self.temp_media_root):
            response = self.client.post(reverse('voice_text_chat_api'), {
                'session_id': str(session.session_id),
                'text': 'N 90 P 42 K 43 temperature 20.8 humidity 82 ph 6.5 rainfall 202.9 crop recommend',
            })

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['prediction'], 'rice')
        self.assertEqual(payload['intent'], 'crop_prediction')
        self.assertFalse(payload['fallback_to_text'])
        self.assertEqual(VoiceConversationTurn.objects.filter(session=session).count(), 2)

    def test_voice_audio_chat_api_returns_low_confidence_fallback(self):
        self._login_voice_user()
        session = VoiceConversationSession.objects.create(user=self.user, title='HTTP Voice Session')
        audio_file = SimpleUploadedFile('voice.webm', b'fake-audio', content_type='audio/webm')

        with patch(
            'home.views.SpeechRecognitionService.transcribe_audio',
            return_value=ASRResult(
                transcript='',
                confidence=0.12,
                language='te-IN',
                provider='fallback',
                raw={'reason': 'test'},
            ),
        ):
            response = self.client.post(reverse('voice_audio_chat_api'), {
                'session_id': str(session.session_id),
                'audio': audio_file,
            })

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['fallback_to_text'])
        self.assertTrue(payload['low_confidence'])
        self.assertEqual(payload['intent'], 'fallback_to_text')
        self.assertEqual(VoiceConversationTurn.objects.filter(session=session, role='system').count(), 1)


class EnvLoadingTests(TestCase):
    def test_load_env_file_sets_missing_environment_values(self):
        temp_dir = tempfile.mkdtemp()
        env_path = os.path.join(temp_dir, '.env')
        try:
            with open(env_path, 'w', encoding='utf-8') as file_obj:
                file_obj.write('NVIDIA_PARAKEET_ASR_URL=https://example.com/asr\n')
                file_obj.write('CONVERSATION_AI_API_URL="https://example.com/ai"\n')

            previous_asr = os.environ.pop('NVIDIA_PARAKEET_ASR_URL', None)
            previous_ai = os.environ.pop('CONVERSATION_AI_API_URL', None)
            load_env_file(env_path)

            self.assertEqual(os.environ.get('NVIDIA_PARAKEET_ASR_URL'), 'https://example.com/asr')
            self.assertEqual(os.environ.get('CONVERSATION_AI_API_URL'), 'https://example.com/ai')
        finally:
            if previous_asr is not None:
                os.environ['NVIDIA_PARAKEET_ASR_URL'] = previous_asr
            else:
                os.environ.pop('NVIDIA_PARAKEET_ASR_URL', None)

            if previous_ai is not None:
                os.environ['CONVERSATION_AI_API_URL'] = previous_ai
            else:
                os.environ.pop('CONVERSATION_AI_API_URL', None)

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_conversation_ai_service_uses_default_endpoint_when_only_api_key_exists(self):
        previous_key = os.environ.get('CONVERSATION_AI_API_KEY')
        previous_url = os.environ.get('CONVERSATION_AI_API_URL')
        try:
            os.environ['CONVERSATION_AI_API_KEY'] = 'demo-key'
            os.environ.pop('CONVERSATION_AI_API_URL', None)

            service = ConversationAIService()

            self.assertEqual(service.endpoint, 'https://integrate.api.nvidia.com/v1/chat/completions')
            self.assertEqual(service.api_key, 'demo-key')
        finally:
            if previous_key is not None:
                os.environ['CONVERSATION_AI_API_KEY'] = previous_key
            else:
                os.environ.pop('CONVERSATION_AI_API_KEY', None)

            if previous_url is not None:
                os.environ['CONVERSATION_AI_API_URL'] = previous_url
            else:
                os.environ.pop('CONVERSATION_AI_API_URL', None)

    def test_model_specific_nvidia_keys_override_shared_key(self):
        previous_values = {
            'NVIDIA_API_KEY': os.environ.get('NVIDIA_API_KEY'),
            'NVIDIA_PARAKEET_API_KEY': os.environ.get('NVIDIA_PARAKEET_API_KEY'),
            'NVIDIA_MAGPIE_API_KEY': os.environ.get('NVIDIA_MAGPIE_API_KEY'),
        }
        try:
            os.environ['NVIDIA_API_KEY'] = 'shared-key'
            os.environ['NVIDIA_PARAKEET_API_KEY'] = 'parakeet-key'
            os.environ['NVIDIA_MAGPIE_API_KEY'] = 'magpie-key'

            asr_service = SpeechRecognitionService()
            tts_service = TextToSpeechService()

            self.assertEqual(asr_service.api_key, 'parakeet-key')
            self.assertEqual(tts_service.api_key, 'magpie-key')
        finally:
            for key, value in previous_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_asr_service_normalizes_nested_result_shape(self):
        service = SpeechRecognitionService()

        transcript, confidence, language = service._normalize_asr_payload(
            {
                'result': {
                    'text': 'తెలుగులో పరీక్ష',
                    'confidence': '0.91',
                    'language_code': 'te-IN',
                }
            },
            'te-IN',
        )

        self.assertEqual(transcript, 'తెలుగులో పరీక్ష')
        self.assertEqual(confidence, 0.91)
        self.assertEqual(language, 'te-IN')

    def test_asr_service_normalizes_predictions_shape(self):
        service = SpeechRecognitionService()

        transcript, confidence, language = service._normalize_asr_payload(
            {
                'predictions': [
                    {
                        'transcript': 'nitrogen 90 phosphorus 42',
                        'score': 0.77,
                        'language': 'en-US',
                    }
                ]
            },
            'te-IN',
        )

        self.assertEqual(transcript, 'nitrogen 90 phosphorus 42')
        self.assertEqual(confidence, 0.77)
        self.assertEqual(language, 'en-US')

    def test_asr_service_is_not_vosk_configured_without_model(self):
        previous_model_path = os.environ.get('VOSK_MODEL_PATH')
        try:
            os.environ.pop('VOSK_MODEL_PATH', None)
            service = SpeechRecognitionService()
            self.assertFalse(service.is_vosk_configured())
        finally:
            if previous_model_path is not None:
                os.environ['VOSK_MODEL_PATH'] = previous_model_path


class ApiAuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = userProfile.objects.create(
            name='Secure User',
            email='secure@example.com',
            password=make_password('Password1'),
            confirm_password='',
            mobile='9000000010',
            status='activated',
        )

    def test_login_json_returns_jwt_token(self):
        response = self.client.post(
            reverse('api_token_obtain_view'),
            {'email': self.user.email, 'password': 'Password1'},
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('token', payload)
        self.assertEqual(payload['user']['role'], 'user')
