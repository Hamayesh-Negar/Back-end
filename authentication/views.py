from django.contrib.auth import logout, login
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.serializers import CustomTokenObtainPairSerializer, RegisterSerializer, LoginSerializer
from user.serializers import UserSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @staticmethod
    def post(request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token_serializer = CustomTokenObtainPairSerializer()
            token_data = token_serializer.get_token(user)
            return Response({
                'access': str(token_data),
                'refresh': str(token_data),
                'user': UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    @staticmethod
    def post(request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            token_serializer = CustomTokenObtainPairSerializer()
            token_data = token_serializer.get_token(user)
            login(request, user)
            return Response({
                'access': str(token_data),
                'refresh': str(token_data),
                'user': UserSerializer(user).data,
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            logout(request)
            return Response(
                {'status': True, 'detail': "Successfully logged out."},
                status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
