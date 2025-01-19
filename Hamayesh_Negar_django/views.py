from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

@api_view(['POST'])
def health_check(request):
    return Response(
        {"status": "200 OK"},
        status=status.HTTP_200_OK
    )