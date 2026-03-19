import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    """Custom manager for User model."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user with given email and password."""
        if not email:
            raise ValueError("Email address is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with given email and password."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model with email as username field."""

    GENDER_CHOICES = [
        ("M", "Male"),
        ("F", "Female"),
        ("O", "Other"),
        ("P", "Prefer not to say"),
    ]

    ROLE_CHOICES = [
        ("user", "User"),
        ("admin", "Admin"),
        ("moderator", "Moderator"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="ID",
    )

    # Fix related_name conflicts with Django's auth.User
    groups = models.ManyToManyField(
        "auth.Group",
        verbose_name="groups",
        blank=True,
        help_text="The groups this user belongs to.",
        related_name="beat_user_set",
        related_query_name="beat_user",
    )

    user_permissions = models.ManyToManyField(
        "auth.Permission",
        verbose_name="user permissions",
        blank=True,
        help_text="Specific permissions for this user.",
        related_name="beat_user_set",
        related_query_name="beat_user",
    )

    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message="Phone number must be entered in format: '+999999999'. Up to 15 digits allowed.",
    )

    # Required fields
    email = models.EmailField("Email address", unique=True)
    first_name = models.CharField("First name", max_length=150)
    last_name = models.CharField("Last name", max_length=150)

    # Optional fields
    birth_date = models.DateField("Birth date", null=True, blank=True)
    phone_number = models.CharField(
        "Phone number", validators=[phone_regex], max_length=17, blank=True
    )
    gender = models.CharField(
        "Gender", max_length=1, choices=GENDER_CHOICES, blank=True
    )
    avatar = models.ImageField("Avatar", upload_to="avatars/", blank=True, null=True)

    # Role
    role = models.CharField(
        "Role",
        max_length=20,
        choices=ROLE_CHOICES,
        default="user",
    )

    # System fields
    is_active = models.BooleanField("Active", default=True)
    is_staff = models.BooleanField("Staff status", default=False)
    date_joined = models.DateTimeField("Date joined", default=timezone.now)
    email_verified = models.BooleanField("Email verified", default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        db_table = "beat_auth_user"

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def full_name(self):
        return self.get_full_name()

    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return None


from .password_reset import PasswordReset  # noqa
from .session import UserSession  # noqa

__all__ = [
    "User",
    "UserSession",
    "PasswordReset",
]
