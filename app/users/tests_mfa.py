"""Segundo factor por correo: el login no debe emitir tokens sin código.

Estas pruebas cubren el contrato completo porque el fallo aquí no es un pixel
torcido: o deja entrar a quien no debe, o deja fuera a todo el mundo.
"""

from datetime import timedelta
from unittest import mock

from apps.models import APIKey, Application
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import User
from users.models.mfa import EmailOtp, TrustedDevice

LOGIN_URL = "/api/auth/login/"
VERIFY_URL = "/api/auth/mfa/verify/"
RESEND_URL = "/api/auth/mfa/resend/"
PASSWORD = "Sup3rSecreta!"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MfaLoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="lmendoza@projects.ec",
            password=PASSWORD,
            first_name="Luis",
            last_name="Mendoza",
        )
        self.app_mfa = Application.objects.create(
            name="Atlas", code="atlas", enforce_mfa=True
        )
        self.app_plain = Application.objects.create(
            name="Metis", code="metis", enforce_mfa=False
        )
        self.key_mfa = APIKey.objects.create(application=self.app_mfa, name="test")
        self.key_plain = APIKey.objects.create(application=self.app_plain, name="test")
        self.client = APIClient()

    # ── Helpers ─────────────────────────────────────────────────────────────
    def login(self, key=None, **extra):
        return self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": PASSWORD, **extra},
            format="json",
            HTTP_X_API_KEY=(key or self.key_mfa).key,
        )

    def current_code(self):
        """Reproduce el código del correo leyendo el cuerpo del mensaje."""
        body = mail.outbox[-1].body
        digits = [w for w in body.split() if w.isdigit() and len(w) == 6]
        return digits[0]

    # ── Compatibilidad con los productos sin MFA ────────────────────────────
    def test_login_sin_mfa_devuelve_tokens_como_siempre(self):
        response = self.login(key=self.key_plain)
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertNotIn("mfa_required", response.data)
        self.assertEqual(len(mail.outbox), 0)

    # ── Paso 1 ──────────────────────────────────────────────────────────────
    def test_login_con_mfa_no_emite_tokens(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["mfa_required"])
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn("mfa_token", response.data)
        self.assertEqual(response.data["email_hint"], "l******a@projects.ec")
        self.assertEqual(len(mail.outbox), 1)

    def test_password_incorrecta_no_manda_codigo(self):
        response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": "otra"},
            format="json",
            HTTP_X_API_KEY=self.key_mfa.key,
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "no_active_account")
        self.assertEqual(len(mail.outbox), 0)

    def test_el_codigo_no_se_guarda_en_claro(self):
        self.login()
        otp = EmailOtp.objects.get()
        self.assertNotIn(self.current_code(), otp.code_hash)
        self.assertTrue(otp.check_code(self.current_code()))

    def test_login_repetido_no_bombardea_el_buzon(self):
        self.login()
        self.login()
        self.login()
        self.assertEqual(len(mail.outbox), 1)

    def _abrir_ventana_de_revision(self, dias=7):
        self.user.review_account_until = timezone.now() + timedelta(days=dias)
        self.user.save(update_fields=["review_account_until"])

    def test_cuenta_de_revision_entra_sin_codigo(self):
        """El revisor de Apple/Google no tiene acceso a ese buzón."""
        self._abrir_ventana_de_revision()
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertNotIn("mfa_required", response.data)
        self.assertEqual(len(mail.outbox), 0)

    def test_la_ventana_caducada_vuelve_a_pedir_codigo(self):
        """Una exención que no caduca es una cuenta sin segundo factor."""
        self.user.review_account_until = timezone.now() - timedelta(minutes=1)
        self.user.save(update_fields=["review_account_until"])
        self.assertTrue(self.login().data.get("mfa_required"))

    def test_la_ventana_no_es_el_estado_por_defecto(self):
        self.assertIsNone(self.user.review_account_until)
        self.assertFalse(self.user.is_review_account)
        self.assertTrue(self.login().data.get("mfa_required"))

    def test_la_sesion_dice_que_es_cuenta_de_revision(self):
        """El cliente lo necesita para no plantarle el muro de la passkey."""
        self._abrir_ventana_de_revision()
        response = self.login()
        self.assertTrue(response.data["user"]["is_review_account"])

    # ── Paso 2 ──────────────────────────────────────────────────────────────
    def test_codigo_correcto_emite_tokens(self):
        challenge = self.login().data
        response = self.client.post(
            VERIFY_URL,
            {"mfa_token": challenge["mfa_token"], "code": self.current_code()},
            format="json",
            HTTP_X_API_KEY=self.key_mfa.key,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], self.user.email)
        self.assertEqual(EmailOtp.objects.get().status, EmailOtp.USED)

    def test_codigo_incorrecto_descuenta_intentos(self):
        challenge = self.login().data
        response = self.client.post(
            VERIFY_URL,
            {"mfa_token": challenge["mfa_token"], "code": "000000"},
            format="json",
            HTTP_X_API_KEY=self.key_mfa.key,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "mfa_invalid_code")
        self.assertEqual(response.data["attempts_left"], EmailOtp.MAX_ATTEMPTS - 1)

    def test_codigo_de_un_solo_uso(self):
        challenge = self.login().data
        code = self.current_code()
        payload = {"mfa_token": challenge["mfa_token"], "code": code}
        self.client.post(
            VERIFY_URL, payload, format="json", HTTP_X_API_KEY=self.key_mfa.key
        )
        repeat = self.client.post(
            VERIFY_URL, payload, format="json", HTTP_X_API_KEY=self.key_mfa.key
        )
        self.assertEqual(repeat.status_code, 401)
        self.assertEqual(repeat.data["code"], "mfa_restart")

    def test_agotar_intentos_invalida_el_desafio(self):
        challenge = self.login().data
        for _ in range(EmailOtp.MAX_ATTEMPTS):
            last = self.client.post(
                VERIFY_URL,
                {"mfa_token": challenge["mfa_token"], "code": "000000"},
                format="json",
                HTTP_X_API_KEY=self.key_mfa.key,
            )
        self.assertEqual(last.status_code, 401)
        self.assertEqual(EmailOtp.objects.get().status, EmailOtp.CANCELLED)

    def test_codigo_caducado_no_sirve(self):
        challenge = self.login().data
        code = self.current_code()
        EmailOtp.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        response = self.client.post(
            VERIFY_URL,
            {"mfa_token": challenge["mfa_token"], "code": code},
            format="json",
            HTTP_X_API_KEY=self.key_mfa.key,
        )
        self.assertEqual(response.status_code, 401)

    def test_token_manipulado_no_sirve(self):
        self.login()
        response = self.client.post(
            VERIFY_URL,
            {"mfa_token": "no-es-un-token", "code": self.current_code()},
            format="json",
            HTTP_X_API_KEY=self.key_mfa.key,
        )
        self.assertEqual(response.status_code, 401)

    def test_tope_de_correos_por_hora(self):
        """Repetir el login cada 61 s no puede ser un cañón de correo."""
        from users.utils.mfa import MAX_OTPS_PER_HOUR

        for _ in range(MAX_OTPS_PER_HOUR):
            self.login()
            # Se salta el cooldown para forzar la emisión de uno nuevo.
            EmailOtp.objects.update(
                last_sent_at=timezone.now()
                - timedelta(seconds=EmailOtp.RESEND_COOLDOWN_SECONDS + 1)
            )
        self.assertEqual(len(mail.outbox), MAX_OTPS_PER_HOUR)

        response = self.login()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["code"], "mfa_rate_limited")
        self.assertEqual(len(mail.outbox), MAX_OTPS_PER_HOUR)

    def test_el_desafio_no_se_canjea_desde_otro_producto(self):
        challenge = self.login().data
        otra_app = Application.objects.create(
            name="Delta", code="delta", enforce_mfa=True
        )
        otra_key = APIKey.objects.create(application=otra_app, name="test")
        response = self.client.post(
            VERIFY_URL,
            {"mfa_token": challenge["mfa_token"], "code": self.current_code()},
            format="json",
            HTTP_X_API_KEY=otra_key.key,
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "mfa_restart")

    # ── Reenvío ─────────────────────────────────────────────────────────────
    def test_reenvio_respeta_el_cooldown(self):
        challenge = self.login().data
        response = self.client.post(
            RESEND_URL,
            {"mfa_token": challenge["mfa_token"]},
            format="json",
            HTTP_X_API_KEY=self.key_mfa.key,
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(mail.outbox), 1)

    def test_reenvio_pasado_el_cooldown_cambia_el_codigo(self):
        challenge = self.login().data
        primer_codigo = self.current_code()
        EmailOtp.objects.update(
            last_sent_at=timezone.now()
            - timedelta(seconds=EmailOtp.RESEND_COOLDOWN_SECONDS + 1)
        )
        response = self.client.post(
            RESEND_URL,
            {"mfa_token": challenge["mfa_token"]},
            format="json",
            HTTP_X_API_KEY=self.key_mfa.key,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)
        self.assertNotEqual(primer_codigo, self.current_code())
        self.assertFalse(EmailOtp.objects.get().check_code(primer_codigo))

    def test_reenvio_fallido_no_mata_el_codigo_vigente(self):
        """Si el correo no sale, el usuario conserva el que sí le llegó."""
        challenge = self.login().data
        vigente = self.current_code()
        EmailOtp.objects.update(
            last_sent_at=timezone.now()
            - timedelta(seconds=EmailOtp.RESEND_COOLDOWN_SECONDS + 1)
        )
        with mock.patch(
            "users.tasks.send_mfa_code_email", side_effect=RuntimeError("Resend caído")
        ):
            response = self.client.post(
                RESEND_URL,
                {"mfa_token": challenge["mfa_token"]},
                format="json",
                HTTP_X_API_KEY=self.key_mfa.key,
            )
        self.assertEqual(response.status_code, 503)
        self.assertTrue(EmailOtp.objects.get().check_code(vigente))

    def test_reenvio_no_reinicia_los_intentos(self):
        challenge = self.login().data
        self.client.post(
            VERIFY_URL,
            {"mfa_token": challenge["mfa_token"], "code": "000000"},
            format="json",
            HTTP_X_API_KEY=self.key_mfa.key,
        )
        EmailOtp.objects.update(
            last_sent_at=timezone.now()
            - timedelta(seconds=EmailOtp.RESEND_COOLDOWN_SECONDS + 1)
        )
        self.client.post(
            RESEND_URL,
            {"mfa_token": challenge["mfa_token"]},
            format="json",
            HTTP_X_API_KEY=self.key_mfa.key,
        )
        self.assertEqual(EmailOtp.objects.get().attempts, 1)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class TrustedDeviceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="lmendoza@projects.ec",
            password=PASSWORD,
            first_name="Luis",
            last_name="Mendoza",
        )
        self.application = Application.objects.create(
            name="Atlas", code="atlas", enforce_mfa=True
        )
        self.key = APIKey.objects.create(application=self.application, name="test")
        self.client = APIClient()

    def _full_login(self, remember=True):
        challenge = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": PASSWORD},
            format="json",
            HTTP_X_API_KEY=self.key.key,
        ).data
        code = [
            w for w in mail.outbox[-1].body.split() if w.isdigit() and len(w) == 6
        ][0]
        return self.client.post(
            VERIFY_URL,
            {
                "mfa_token": challenge["mfa_token"],
                "code": code,
                "remember_device": remember,
                "device_name": "PC de recepción",
            },
            format="json",
            HTTP_X_API_KEY=self.key.key,
        ).data

    def test_recordar_equipo_devuelve_token_opaco(self):
        data = self._full_login()
        self.assertIn("device_token", data)
        device = TrustedDevice.objects.get()
        self.assertNotEqual(device.token_hash, data["device_token"])
        self.assertEqual(device.device_name, "PC de recepción")

    def test_sin_recordar_no_se_crea_dispositivo(self):
        data = self._full_login(remember=False)
        self.assertNotIn("device_token", data)
        self.assertEqual(TrustedDevice.objects.count(), 0)

    def test_equipo_de_confianza_se_salta_el_codigo(self):
        token = self._full_login()["device_token"]
        mail.outbox.clear()
        response = self.client.post(
            LOGIN_URL,
            {
                "email": self.user.email,
                "password": PASSWORD,
                "device_token": token,
            },
            format="json",
            HTTP_X_API_KEY=self.key.key,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertEqual(len(mail.outbox), 0)

    def test_token_de_otro_usuario_no_vale(self):
        token = self._full_login()["device_token"]
        otro = User.objects.create_user(
            email="otro@projects.ec", password=PASSWORD, first_name="O", last_name="P"
        )
        response = self.client.post(
            LOGIN_URL,
            {"email": otro.email, "password": PASSWORD, "device_token": token},
            format="json",
            HTTP_X_API_KEY=self.key.key,
        )
        self.assertTrue(response.data.get("mfa_required"))

    def test_token_de_otro_producto_no_vale(self):
        token = self._full_login()["device_token"]
        otra_app = Application.objects.create(
            name="Delta", code="delta", enforce_mfa=True
        )
        otra_key = APIKey.objects.create(application=otra_app, name="test")
        response = self.client.post(
            LOGIN_URL,
            {
                "email": self.user.email,
                "password": PASSWORD,
                "device_token": token,
            },
            format="json",
            HTTP_X_API_KEY=otra_key.key,
        )
        self.assertTrue(response.data.get("mfa_required"))

    def test_dispositivo_caducado_vuelve_a_pedir_codigo(self):
        token = self._full_login()["device_token"]
        TrustedDevice.objects.update(expires_at=timezone.now() - timedelta(days=1))
        response = self.client.post(
            LOGIN_URL,
            {
                "email": self.user.email,
                "password": PASSWORD,
                "device_token": token,
            },
            format="json",
            HTTP_X_API_KEY=self.key.key,
        )
        self.assertTrue(response.data.get("mfa_required"))

    def test_cambiar_contrasena_revoca_los_equipos(self):
        self._full_login()
        self.assertEqual(TrustedDevice.objects.filter(revoked_at=None).count(), 1)
        from users.serializers.password import revoke_trust_after_password_change

        self.user.set_password("OtraDistinta1!")
        self.user.save()
        revoke_trust_after_password_change(self.user)
        self.assertEqual(TrustedDevice.objects.filter(revoked_at=None).count(), 0)
