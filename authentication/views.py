from django.contrib.auth import logout, login, get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import PasswordResetTokenGenerator
import logging

from authentication.serializers import (
    CustomTokenObtainPairSerializer, RegisterSerializer, LoginSerializer,
    ForgetPasswordSerializer, ResetPasswordSerializer
)
from user.serializers import UserSerializer, UserPreferenceSerializer
from user.models import UserPreference
from rest_framework_simplejwt.views import TokenObtainPairView

User = get_user_model()
logger = logging.getLogger(__name__)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @staticmethod
    def post(request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            login(request, user)
            try:
                preference = UserPreference.objects.select_related(
                    'selected_conference').get(user=user)
                preference_data = UserPreferenceSerializer(preference).data
            except UserPreference.DoesNotExist:
                preference_data = None

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data,
                'preference': preference_data,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    @staticmethod
    def post(request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            refresh = RefreshToken.for_user(user)
            login(request, user)

            try:
                preference = UserPreference.objects.select_related(
                    'selected_conference').get(user=user)
                preference_data = UserPreferenceSerializer(preference).data
            except UserPreference.DoesNotExist:
                preference_data = None

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data,
                'preference': preference_data,
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            logout(request)
            return Response(
                {'status': True, 'detail': "با موفقیت خارج شدید."},
                status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class VerifyTokenView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):

        return Response({
            'status': True,
            'detail': "Token is valid.",
        }, status=status.HTTP_200_OK)


class CheckUsernameView(APIView):
    permission_classes = [AllowAny]

    @staticmethod
    def get(request):
        username = request.query_params.get('username', '').strip()

        if not username:
            return Response({
                'error': 'Username parameter is required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        normalized_username = username.lower()

        is_taken = User.objects.filter(
            username__iexact=normalized_username).exists()

        return Response({
            'username': username,
            'is_available': not is_taken,
        }, status=status.HTTP_200_OK)


class ForgetPasswordView(APIView):
    permission_classes = [AllowAny]

    @staticmethod
    def post(request):
        serializer = ForgetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)

                token_generator = PasswordResetTokenGenerator()
                token = token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))

                reset_url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

                context = {
                    'user': user,
                    'reset_url': reset_url,
                    'reset_token': token,
                    'uid': uid,
                }

                html_message = render_to_string(
                    'forget_password_email.html', context)

                email_msg = EmailMessage(
                    subject='بازیابی رمزعبور - Hamayesh Negar',
                    body=html_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                email_msg.content_subtype = 'html'

                email_msg.send(fail_silently=False)

                return Response({
                    'status': True,
                    'detail': 'ایمیل بازیابی رمزعبور برای شما ارسال شده است.'
                }, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error sending reset email: {str(e)}")
                return Response({
                    'status': False,
                    'detail': 'خطا در ارسال ایمیل. لطفاً دوباره تلاش کنید.',
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    @staticmethod
    def post(request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            uid = request.data.get('uid')
            token = serializer.validated_data['token']
            new_password = serializer.validated_data['new_password']

            try:
                user_id = force_str(urlsafe_base64_decode(uid))
                user = User.objects.get(pk=user_id)

                token_generator = PasswordResetTokenGenerator()
                if not token_generator.check_token(user, token):
                    return Response({
                        'status': False,
                        'detail': 'لینک بازیابی رمزعبور نامعتبر یا منقضی شده است.',
                    }, status=status.HTTP_400_BAD_REQUEST)

                user.set_password(new_password)
                user.save()

                return Response({
                    'status': True,
                    'detail': 'رمزعبور با موفقیت تغییر یافت.',
                }, status=status.HTTP_200_OK)

            except User.DoesNotExist:
                return Response({
                    'status': False,
                    'detail': 'کاربر یافت نشد.',
                }, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                logger.error(f"Error resetting password: {str(e)}")
                return Response({
                    'status': False,
                    'detail': 'خطا در بازیابی رمزعبور. لطفاً دوباره تلاش کنید.',
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
