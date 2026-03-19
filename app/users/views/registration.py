from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from ..models import User
from ..serializers import UserRegistrationSerializer, UserUpdateSerializer
from ..throttles import RegisterRateThrottle


@extend_schema_view(
    post=extend_schema(description="Register a new user account", tags=["Registration"])
)
class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint."""

    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def create(self, request, *args, **kwargs):
        """Create user, issue JWT tokens, and return authentication data."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens mirroring CustomTokenObtainPairSerializer claims
        refresh = RefreshToken.for_user(user)
        for token in (refresh, refresh.access_token):
            token["email"] = user.email
            token["first_name"] = user.first_name
            token["last_name"] = user.last_name
            token["full_name"] = user.get_full_name()
            token["is_staff"] = user.is_staff
            token["email_verified"] = user.email_verified
            token["role"] = user.role
            token["user_id"] = str(user.id)

        return Response(
            {
                "message": "User registered successfully",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "full_name": user.get_full_name(),
                    "is_staff": user.is_staff,
                    "email_verified": user.email_verified,
                    "role": user.role,
                    "date_joined": user.date_joined,
                    "last_login": user.last_login,
                    "avatar": None,
                },
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    put=extend_schema(
        description="Update user profile information", tags=["Registration"]
    ),
    patch=extend_schema(
        description="Partially update user profile information",
        tags=["Registration"],
    ),
)
class UserUpdateView(generics.UpdateAPIView):
    """User profile update endpoint."""

    serializer_class = UserUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Return current authenticated user."""
        return self.request.user

    def update(self, request, *args, **kwargs):
        """Update user profile and return updated data."""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(
            {
                "message": "Profile updated successfully",
                "user": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
